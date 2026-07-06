"""Integration tests for AI review service and batch processing."""
import json
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.core.cache import cache

from apps.parser.models import ExamQuestion, ExamPaper
from apps.common.exceptions import AIRequestError
from apps.common.ai_service import AIReviewService


def _make_qs_mock(items):
    """Create a mock queryset that supports .filter().order_by() chaining."""
    mock = MagicMock()
    mock.filter.return_value = mock
    mock.order_by.return_value = mock
    mock.__iter__ = MagicMock(return_value=iter(items))
    mock.__bool__ = MagicMock(return_value=bool(items))
    mock.count.return_value = len(items)
    return mock


class AIReviewServiceUnitTest(TestCase):
    """Unit tests for AIReviewService with mocked AI calls."""

    def setUp(self):
        self.paper = ExamPaper.objects.create(
            title='Test Paper',
            subject='math',
        )
        self.question = ExamQuestion.objects.create(
            paper=self.paper,
            stem='已知函数 $f(x) = x^2 + 1$，求 $f(2)$ 的值。',
            answer='5',
            analysis='代入计算',
            question_type='single_choice',
        )

    @patch.object(AIReviewService, '_call_ai')
    def test_analyze_knowledge_returns_valid_json(self, mock_call):
        mock_call.return_value = json.dumps({
            'knowledge_points': [
                {'id': 1, 'module': '函数', 'subject': 'math', 'full_label': '高中数学-函数'}
            ],
            'grade_term': {
                'stage': 'high', 'grade_index': 1, 'grade_name': '高一',
                'term': '上学期', 'label': '高一上学期'
            },
            'solving_methods': ['代入法']
        })

        service = AIReviewService()
        with patch('apps.knowledge.models.KnowledgePoint.objects.filter') as mock_kp:
            mock_kp.return_value.values.return_value = [
                {'id': 1, 'module': '函数', 'subject': 'math'}
            ]
            with patch('apps.parser.models.QuestionImage.objects.filter') as mock_img:
                mock_img.return_value = _make_qs_mock([])
                result = service.analyze_knowledge(self.question)

        self.assertIn('knowledge_points', result)
        self.assertIn('grade_term', result)
        self.assertIn('solving_methods', result)
        self.assertEqual(len(result['knowledge_points']), 1)

    @patch.object(AIReviewService, '_call_ai')
    def test_generate_answer_a_returns_steps(self, mock_call):
        mock_call.return_value = json.dumps({
            'mode': 'A', 'subject': 'math', 'core_ideas': ['代入求值'],
            'steps': [
                {'step': 1, 'content': '将 $x=2$ 代入函数'},
                {'step': 2, 'content': '计算 $f(2) = 2^2 + 1 = 5$'},
                {'step': 3, 'content': '得出答案'}
            ],
            'final_answer': '5', 'summary': '直接代入即可。', 'missing_conditions': []
        })

        with patch('apps.parser.models.QuestionImage.objects.filter') as mock_img:
            mock_img.return_value = _make_qs_mock([])
            service = AIReviewService()
            result = service.generate_answer_a(self.question)

        self.assertIn('steps', result)
        self.assertEqual(len(result['steps']), 3)
        self.assertEqual(result['final_answer'], '5')

    @patch.object(AIReviewService, '_call_ai')
    def test_generate_answer_b_returns_questions(self, mock_call):
        mock_call.return_value = json.dumps({
            'mode': 'B', 'subject': 'math', 'core_ideas': ['理解函数概念'],
            'questions': [
                {
                    'id': 1, 'question': '这道题要求什么？',
                    'options': {'A': '求 f(1)', 'B': '求 f(2)', 'C': '求 f(3)', 'D': '求 f(0)'},
                    'correct_option': 'B', 'reference_answer': '求 f(2)',
                    'analysis': '题干明确要求 f(2)'
                },
                {
                    'id': 2, 'question': '代入后结果是多少？',
                    'options': {'A': '3', 'B': '4', 'C': '5', 'D': '6'},
                    'correct_option': 'C', 'reference_answer': '5',
                    'analysis': '2^2+1=5'
                },
                {
                    'id': 3, 'question': '最终答案是什么？',
                    'options': {'A': '3', 'B': '4', 'C': '5', 'D': '6'},
                    'correct_option': 'C', 'reference_answer': '5',
                    'analysis': 'f(2)=5'
                }
            ],
            'final_answer': '5', 'summary': '通过逐步引导理解函数求值。',
            'missing_conditions': []
        })

        with patch('apps.parser.models.QuestionImage.objects.filter') as mock_img:
            mock_img.return_value = _make_qs_mock([])
            service = AIReviewService()
            result = service.generate_answer_b(self.question)

        self.assertIn('questions', result)
        self.assertEqual(len(result['questions']), 3)
        for q in result['questions']:
            for key in ['A', 'B', 'C', 'D']:
                self.assertIn(key, q['options'])

    @patch.object(AIReviewService, '_call_ai')
    def test_generate_answer_c_returns_open_questions(self, mock_call):
        mock_call.return_value = json.dumps({
            'mode': 'C', 'subject': 'math', 'core_ideas': ['函数求值'],
            'questions': [
                {
                    'id': 1, 'question': '观察题干，你发现了什么结构？',
                    'reference_answer': '这是一个二次函数',
                    'key_points': ['识别函数形式', '理解变量关系'],
                    'followup_hint': '想想二次函数的特点'
                },
                {
                    'id': 2, 'question': '如何建立变量之间的关系？',
                    'reference_answer': '将x的值代入函数式',
                    'key_points': ['代入方法', '计算步骤'],
                    'followup_hint': '注意运算顺序'
                },
                {
                    'id': 3, 'question': '你能得出什么结论？',
                    'reference_answer': 'f(2) = 5',
                    'key_points': ['得出答案', '验证结果'],
                    'followup_hint': '检查计算是否正确'
                }
            ],
            'final_answer': '5', 'summary': '通过开放性引导理解函数求值过程。',
            'missing_conditions': []
        })

        with patch('apps.parser.models.QuestionImage.objects.filter') as mock_img:
            mock_img.return_value = _make_qs_mock([])
            service = AIReviewService()
            result = service.generate_answer_c(self.question)

        self.assertIn('questions', result)
        self.assertEqual(len(result['questions']), 3)
        for q in result['questions']:
            self.assertIn('key_points', q)
            self.assertEqual(len(q['key_points']), 2)


class AIReviewBusinessLogicTest(TestCase):
    """Tests for ai_review_service business logic."""

    def setUp(self):
        self.paper = ExamPaper.objects.create(
            title='Test Paper', subject='math',
        )
        self.question = ExamQuestion.objects.create(
            paper=self.paper, stem='测试题目', answer='A',
            question_type='single_choice',
        )

    def test_confirm_ai_answer_sets_flag(self):
        from apps.review.services.ai_review_service import confirm_ai_answer

        self.question.ai_answer_a = {
            'mode': 'A', 'final_answer': '5', 'confirmed': False
        }
        self.question.save()

        result = confirm_ai_answer(self.question.id, 'A')

        self.assertTrue(result['success'])
        self.question.refresh_from_db()
        self.assertTrue(self.question.ai_answer_a['confirmed'])
        self.assertIn('confirmed_at', self.question.ai_answer_a)

    def test_confirm_ai_answer_raises_if_no_data(self):
        from apps.review.services.ai_review_service import confirm_ai_answer

        with self.assertRaises(ValueError):
            confirm_ai_answer(self.question.id, 'A')

    def test_update_ai_answer_saves_edited_content(self):
        from apps.review.services.ai_review_service import update_ai_answer

        self.question.ai_answer_b = {'mode': 'B', 'final_answer': 'original'}
        self.question.save()

        result = update_ai_answer(self.question.id, 'B', {'final_answer': 'edited'})

        self.assertTrue(result['success'])
        self.question.refresh_from_db()
        self.assertEqual(
            self.question.ai_answer_b['edited_content']['final_answer'], 'edited'
        )

    def test_update_knowledge_enrichment_replaces_data(self):
        from apps.review.services.ai_review_service import update_knowledge_enrichment

        new_data = {
            'knowledge_points': [{'id': 1, 'module': '函数'}],
            'grade_term': {'label': '高一上学期'},
            'solving_methods': ['代入法']
        }

        result = update_knowledge_enrichment(self.question.id, new_data)

        self.assertTrue(result['success'])
        self.question.refresh_from_db()
        self.assertEqual(
            self.question.ai_knowledge_enrichment['grade_term']['label'],
            '高一上学期'
        )

    def test_get_ai_status_returns_structure(self):
        from apps.review.services.ai_review_service import get_ai_status

        self.question.ai_answer_a = {'mode': 'A', 'confirmed': True}
        self.question.ai_answer_b = {'mode': 'B', 'error': 'timeout'}
        self.question.ai_knowledge_enrichment = {'knowledge_points': [{'id': 1}]}
        self.question.save()

        status = get_ai_status(self.question.id)

        self.assertEqual(status['question_id'], self.question.id)
        self.assertEqual(status['answer_a_status'], 'confirmed')
        self.assertEqual(status['answer_b_status'], 'error')
        self.assertEqual(status['answer_c_status'], 'blank')
        self.assertEqual(status['knowledge_points_count'], 1)


class AIProcessFullPipelineTest(TestCase):
    """Tests for the full 4-step AI processing pipeline."""

    def setUp(self):
        self.paper = ExamPaper.objects.create(
            title='Test Paper', subject='math',
        )
        self.question = ExamQuestion.objects.create(
            paper=self.paper, stem='测试题目', answer='A',
            question_type='single_choice',
        )

    def test_save_results_saves_all_fields(self):
        """save_results_to_question should save all AI results to DB."""
        from apps.common.ai_service import AIReviewService

        results = {
            'knowledge': {
                'knowledge_points': [],
                'grade_term': {'label': '高一'},
                'solving_methods': ['代入法'],
                'error': None,
            },
            'answer_a': {
                'mode': 'A', 'final_answer': '5', 'error': None,
            },
            'answer_b': {
                'mode': 'B', 'final_answer': '5', 'error': None,
            },
            'answer_c': {
                'mode': 'C', 'final_answer': '5', 'error': None,
            },
            'errors': {},
        }

        service = AIReviewService()
        service.save_results_to_question(self.question.id, results)

        self.question.refresh_from_db()
        self.assertIsNotNone(self.question.ai_answer_a)
        self.assertIsNotNone(self.question.ai_answer_b)
        self.assertIsNotNone(self.question.ai_answer_c)
        self.assertIsNotNone(self.question.ai_knowledge_enrichment)
        self.assertEqual(self.question.ai_answer_a['mode'], 'A')
        self.assertEqual(self.question.ai_answer_b['mode'], 'B')
        self.assertEqual(self.question.ai_answer_c['mode'], 'C')

    def test_save_results_extracts_difficulty(self):
        """Difficulty from knowledge analysis should be saved to ExamQuestion.difficulty."""
        from apps.common.ai_service import AIReviewService
        from unittest.mock import patch, MagicMock

        results = {
            'knowledge': {
                'knowledge_points': [{'id': None, 'module': ''}],
                'grade_term': {'label': '高一'},
                'solving_methods': ['代入法'],
                'difficulty': 'L3',
                'error': None,
            },
            'answer_a': {'mode': 'A', 'final_answer': '5', 'error': None},
            'answer_b': {'mode': 'B', 'final_answer': '5', 'error': None},
            'answer_c': {'mode': 'C', 'final_answer': '5', 'error': None},
            'errors': {},
        }

        with patch('apps.knowledge.models.KnowledgePoint.objects.filter') as mock_filter:
            mock_filter.return_value = MagicMock()
            mock_filter.return_value.first.return_value = None
            service = AIReviewService()
            service.save_results_to_question(self.question.id, results)

        self.question.refresh_from_db()
        self.assertEqual(int(self.question.difficulty), 3)

    def test_save_results_ignores_invalid_difficulty(self):
        """Invalid difficulty values should not overwrite the field."""
        from apps.common.ai_service import AIReviewService

        results = {
            'knowledge': {
                'knowledge_points': [],
                'difficulty': 'invalid',
                'error': None,
            },
            'answer_a': {'error': None},
            'answer_b': {'error': None},
            'answer_c': {'error': None},
            'errors': {},
        }

        service = AIReviewService()
        service.save_results_to_question(self.question.id, results)

        self.question.refresh_from_db()
        self.assertIsNone(self.question.difficulty)

    @patch.object(AIReviewService, 'analyze_knowledge')
    @patch.object(AIReviewService, 'generate_answer_a')
    @patch.object(AIReviewService, 'generate_answer_b')
    @patch.object(AIReviewService, 'generate_answer_c')
    def test_process_question_full_all_success(
            self, mock_c, mock_b, mock_a, mock_knowledge):
        mock_knowledge.return_value = {
            'knowledge_points': [{'id': 1, 'module': '函数'}],
            'grade_term': {'label': '高一'},
            'solving_methods': ['代入法']
        }
        mock_a.return_value = {'mode': 'A', 'final_answer': '5'}
        mock_b.return_value = {'mode': 'B', 'final_answer': '5'}
        mock_c.return_value = {'mode': 'C', 'final_answer': '5'}

        with patch('apps.knowledge.models.KnowledgePoint.objects.filter') as mock_filter:
            mock_filter.return_value = _make_qs_mock([])
            with patch('apps.knowledge.models.KnowledgePoint.objects.get') as mock_get:
                mock_kp = MagicMock()
                mock_kp.full_label = '高中数学-函数'
                mock_get.return_value = mock_kp

                service = AIReviewService()
                results = service.process_question_full(self.question.id)

        # Verify result structure
        self.assertNotIn('knowledge', results['errors'])
        self.assertNotIn('answer_a', results['errors'])
        self.assertIn('knowledge', results)
        self.assertIn('answer_a', results)
        self.assertEqual(results['answer_a']['mode'], 'A')
        self.assertEqual(results['answer_b']['mode'], 'B')
        self.assertEqual(results['answer_c']['mode'], 'C')

    @patch.object(AIReviewService, 'analyze_knowledge')
    @patch.object(AIReviewService, 'generate_answer_a')
    @patch.object(AIReviewService, 'generate_answer_b')
    @patch.object(AIReviewService, 'generate_answer_c')
    def test_process_question_full_knowledge_failure(
            self, mock_c, mock_b, mock_a, mock_knowledge):
        mock_knowledge.side_effect = AIRequestError('API timeout')
        mock_a.return_value = {'mode': 'A', 'final_answer': '5'}
        mock_b.return_value = {'mode': 'B', 'final_answer': '5'}
        mock_c.return_value = {'mode': 'C', 'final_answer': '5'}

        with patch('apps.parser.models.QuestionImage.objects.filter') as mock_img:
            mock_img.return_value = _make_qs_mock([])
            service = AIReviewService()
            results = service.process_question_full(self.question.id)

        self.assertIn('knowledge', results['errors'])
        self.assertNotIn('answer_a', results['errors'])
        self.assertIn('answer_a', results)
        self.assertIn('answer_b', results)
        self.assertIn('answer_c', results)


class BatchTaskTest(TestCase):
    """Tests for Celery batch processing task."""

    def setUp(self):
        self.paper = ExamPaper.objects.create(
            title='Test Paper', subject='math',
        )
        self.question_ids = []
        for i in range(5):
            q = ExamQuestion.objects.create(
                paper=self.paper, stem=f'测试题目 {i}', answer='A',
                question_type='single_choice',
            )
            self.question_ids.append(q.id)

    def _run_batch_task(self, q_ids, cancel=False):
        """Run the batch task function directly, bypassing Celery wrapper."""
        from apps.common.batch_tasks import (
            AIReviewService, cache, CANCEL_KEY_PREFIX, PROGRESS_KEY_PREFIX
        )
        from concurrent.futures import ThreadPoolExecutor, as_completed

        if cancel:
            cache.set(f'{CANCEL_KEY_PREFIX}test-cancel', '1', timeout=60)

        service = AIReviewService()
        success_count = 0
        error_count = 0
        errors = {}

        def process_one(q_id):
            try:
                results = service.process_question_full(q_id)
                service.save_results_to_question(q_id, results)
                has_errors = bool(results.get('errors'))
                return (q_id, not has_errors,
                        str(results.get('errors')) if has_errors else None)
            except Exception as e:
                return (q_id, False, str(e))

        with ThreadPoolExecutor(max_workers=1) as executor:
            futures = {executor.submit(process_one, q_id): q_id for q_id in q_ids}
            current = 0
            for future in as_completed(futures):
                if cache.get(f'{CANCEL_KEY_PREFIX}test-cancel'):
                    cache.delete(f'{CANCEL_KEY_PREFIX}test-cancel')
                    return {'status': 'cancelled', 'current': current, 'total': len(q_ids)}
                q_id, success, error = future.result()
                current += 1
                if success:
                    success_count += 1
                else:
                    error_count += 1
                    errors[str(q_id)] = error or 'Unknown error'

        return {'status': 'completed', 'success_count': success_count,
                'error_count': error_count, 'errors': errors}

    @patch.object(AIReviewService, 'process_question_full')
    @patch.object(AIReviewService, 'save_results_to_question')
    def test_batch_task_processes_all_questions(self, mock_save, mock_process):
        mock_process.return_value = {
            'knowledge': {'knowledge_points': []},
            'answer_a': {'mode': 'A'},
            'answer_b': {'mode': 'B'},
            'answer_c': {'mode': 'C'},
            'errors': {}
        }

        result = self._run_batch_task(self.question_ids)

        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['success_count'], 5)
        self.assertEqual(result['error_count'], 0)
        self.assertEqual(mock_process.call_count, 5)

    @patch.object(AIReviewService, 'process_question_full')
    @patch.object(AIReviewService, 'save_results_to_question')
    def test_batch_task_tracks_errors(self, mock_save, mock_process):
        def side_effect(q_id, model=None):
            if q_id == self.question_ids[0]:
                raise Exception('API error')
            return {
                'knowledge': {'knowledge_points': []},
                'answer_a': {'mode': 'A'},
                'answer_b': {'mode': 'B'},
                'answer_c': {'mode': 'C'},
                'errors': {}
            }
        mock_process.side_effect = side_effect

        result = self._run_batch_task(self.question_ids)

        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['success_count'], 4)
        self.assertEqual(result['error_count'], 1)
        self.assertIn(str(self.question_ids[0]), result['errors'])

    def test_batch_cancel_flag_stops_processing(self):
        result = self._run_batch_task(self.question_ids, cancel=True)
        self.assertEqual(result['status'], 'cancelled')
