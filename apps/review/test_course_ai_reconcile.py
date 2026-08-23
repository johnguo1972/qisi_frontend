from types import SimpleNamespace
from io import StringIO
from unittest.mock import Mock, patch

from django.core.management import call_command
from django.test import SimpleTestCase

from apps.review import tasks


def _question(**overrides):
    values = {
        'ai_probe_result': {
            'grade': '九年级',
            'semester': '上学期',
            'subject': 'physics',
            'question_type': 'single_choice',
            'normalized_text': '题干',
        },
        'ai_knowledge_enrichment': {
            'difficulty': 'L2',
            'knowledge_points': [{'module': '内能'}],
        },
        'difficulty': 2,
        'ai_answer_a': {'mode': 'A', 'final_answer': 'A'},
        'ai_answer_b': {'mode': 'B', 'final_answer': 'A'},
        'ai_answer_c': {'mode': 'C', 'final_answer': 'A'},
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class CourseAIReconcileCompletenessTests(SimpleTestCase):
    def test_probe_with_error_is_missing_even_when_knowledge_and_difficulty_exist(self):
        question = _question(ai_probe_result={'error': 'HTTP 400'})

        self.assertFalse(tasks.is_ai_probe_complete(question))
        self.assertTrue(tasks.is_ai_knowledge_complete(question))

    def test_probe_requires_grade_semester_subject_type_and_normalized_text(self):
        question = _question(ai_probe_result={
            'grade': '九年级',
            'semester': '',
            'subject': 'physics',
            'question_type': 'single_choice',
            'normalized_text': '题干',
        })

        self.assertFalse(tasks.is_ai_probe_complete(question))

    def test_mode_payload_with_error_is_missing(self):
        question = _question(ai_answer_b={'error': 'read_timeout'})

        self.assertFalse(tasks.is_ai_mode_complete(question, 'B'))
        self.assertTrue(tasks.is_ai_mode_complete(question, 'A'))


class CourseAIReconcileQuestionTests(SimpleTestCase):
    @patch('apps.review.tasks._load_reconcile_question')
    @patch('apps.review.tasks._run_reconcile_probe')
    def test_probe_only_task_retries_once_without_running_other_steps(
        self, run_probe, load_question,
    ):
        load_question.side_effect = [
            _question(ai_probe_result={'error': 'schema'}),
            _question(ai_probe_result={'error': 'schema'}),
            _question(),
        ]
        run_probe.side_effect = [
            {'status': 'failed', 'error': 'schema_invalid'},
            {'status': 'complete'},
        ]

        result = tasks.reconcile_course_probe_only_task.run('question-0')

        self.assertEqual(run_probe.call_count, 2)
        self.assertEqual(result['step']['status'], 'complete')
        self.assertEqual(result['step']['attempts'], 2)

    @patch('apps.review.tasks._load_reconcile_question')
    @patch('apps.review.tasks._run_reconcile_mode')
    @patch('apps.review.tasks._run_reconcile_knowledge')
    @patch('apps.review.tasks._run_reconcile_probe')
    def test_only_missing_steps_run_and_each_failure_gets_one_retry(
        self, run_probe, run_knowledge, run_mode, load_question,
    ):
        states = [
            _question(
                ai_probe_result={'error': 'HTTP 400'},
                ai_answer_b=None,
            ),
            _question(ai_probe_result={'error': 'HTTP 503'}, ai_answer_b=None),
            _question(ai_answer_b=None),
            _question(ai_answer_b={'mode': 'B', 'final_answer': 'A'}),
        ]
        load_question.side_effect = states
        run_probe.side_effect = [
            {'status': 'failed', 'error': 'provider_unavailable'},
            {'status': 'complete'},
        ]
        run_mode.return_value = {'status': 'complete'}

        result = tasks.reconcile_course_question_ai('question-1', round_no=1)

        self.assertEqual(run_probe.call_count, 2)
        run_knowledge.assert_not_called()
        run_mode.assert_called_once_with('question-1', 'B')
        self.assertEqual(result['steps']['probe']['attempts'], 2)
        self.assertEqual(result['steps']['A']['status'], 'skipped')
        self.assertEqual(result['steps']['B']['status'], 'complete')
        self.assertEqual(result['steps']['C']['status'], 'skipped')

    @patch('apps.review.tasks._load_reconcile_question')
    @patch('apps.review.tasks._run_reconcile_mode')
    @patch('apps.review.tasks._run_reconcile_knowledge')
    @patch('apps.review.tasks._run_reconcile_probe')
    def test_failed_probe_twice_blocks_modes_and_preserves_failure_reason(
        self, run_probe, run_knowledge, run_mode, load_question,
    ):
        load_question.side_effect = [
            _question(ai_probe_result={'error': 'HTTP 400'}, ai_answer_a=None),
            _question(ai_probe_result={'error': 'HTTP 503'}, ai_answer_a=None),
            _question(ai_probe_result={'error': 'HTTP 503'}, ai_answer_a=None),
        ]
        run_probe.side_effect = [
            {'status': 'failed', 'error': 'provider_unavailable'},
            {'status': 'failed', 'error': 'provider_unavailable'},
        ]

        result = tasks.reconcile_course_question_ai('question-2', round_no=1)

        self.assertEqual(run_probe.call_count, 2)
        run_knowledge.assert_not_called()
        run_mode.assert_not_called()
        self.assertEqual(result['steps']['probe'], {
            'status': 'failed',
            'attempts': 2,
            'error': 'provider_unavailable',
        })
        self.assertEqual(result['steps']['A']['error'], 'probe_incomplete')


class CourseAIReconcileRoundTests(SimpleTestCase):
    @patch('apps.review.tasks._enqueue_course_reconcile_round')
    @patch('apps.review.tasks._set_course_reconcile_status')
    def test_first_round_callback_always_enqueues_second_full_rescan(
        self, set_status, enqueue_round,
    ):
        enqueue_round.return_value = 'round-2-task'

        result = tasks.course_ai_reconcile_round_finished.run(
            [{'question_id': 'q1', 'steps': {'B': {'status': 'failed', 'error': 'read_timeout'}}}],
            'course-1', 'batch-1', 1,
        )

        enqueue_round.assert_called_once_with('course-1', 'batch-1', 2)
        self.assertEqual(result['status'], 'round_2_queued')


class CourseAIReconcileCommandTests(SimpleTestCase):
    @patch('apps.review.tasks.start_course_ai_reconcile.apply_async')
    @patch('apps.review.management.commands.reconcile_course_ai.uuid.uuid4')
    def test_enqueue_command_uses_ai_batch_queue_and_prints_batch_id(
        self, make_uuid, apply_async,
    ):
        make_uuid.return_value = 'batch-123'
        apply_async.return_value = SimpleNamespace(id='starter-task-1')
        stdout = StringIO()

        call_command(
            'reconcile_course_ai',
            course_id='course-1',
            stdout=stdout,
        )

        apply_async.assert_called_once_with(
            args=('course-1', 'batch-123'), queue='ai.batch'
        )
        self.assertIn('batch-123', stdout.getvalue())
        self.assertIn('starter-task-1', stdout.getvalue())

    @patch('apps.review.tasks.get_course_reconcile_status')
    def test_status_command_prints_persisted_failure_details(self, get_status):
        get_status.return_value = {
            'batch_id': 'batch-123',
            'status': 'completed',
            'rounds': {
                '2': {
                    'failures': [{
                        'question_id': 'q1',
                        'step': 'B',
                        'error': 'read_timeout',
                    }],
                },
            },
        }
        stdout = StringIO()

        call_command(
            'course_ai_reconcile_status',
            batch_id='batch-123',
            stdout=stdout,
        )

        self.assertIn('read_timeout', stdout.getvalue())
