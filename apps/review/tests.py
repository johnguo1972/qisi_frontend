"""Integration tests for AI review service and batch processing."""
import json
from types import SimpleNamespace
from unittest.mock import patch, MagicMock
from django.test import TestCase, override_settings
from django.core.cache import cache
from django.urls import reverse
from rest_framework.test import APIClient

from apps.parser.models import ExamQuestion, ExamPaper
from apps.common.exceptions import AIRequestError
from apps.common.ai_service import AIReviewService
from apps.accounts.models import UserAccount
from apps.accounts.roles import grant_user_role
from apps.accounts.services import generate_tokens


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
    @patch.object(AIReviewService, 'solve_mode_with_arbitration')
    def test_process_question_full_all_success(
            self, mock_arbitrate, mock_knowledge):
        mock_knowledge.return_value = {
            'knowledge_points': [{'id': 1, 'module': '函数'}],
            'grade_term': {'label': '高一'},
            'solving_methods': ['代入法']
        }
        mock_arbitrate.side_effect = lambda question, *, mode, **kwargs: MagicMock(
            answer={'mode': mode, 'final_answer': '5'},
            shared_verifier_result=None,
        )

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
    @patch.object(AIReviewService, 'solve_mode_with_arbitration')
    def test_process_question_full_knowledge_failure(
            self, mock_arbitrate, mock_knowledge):
        mock_knowledge.side_effect = AIRequestError('API timeout')
        mock_arbitrate.side_effect = lambda question, *, mode, **kwargs: MagicMock(
            answer={'mode': mode, 'final_answer': '5'},
            shared_verifier_result=None,
        )

        with patch('apps.parser.models.QuestionImage.objects.filter') as mock_img:
            mock_img.return_value = _make_qs_mock([])
            service = AIReviewService()
            results = service.process_question_full(self.question.id)

        self.assertIn('knowledge', results['errors'])
        self.assertNotIn('answer_a', results['errors'])
        self.assertIn('answer_a', results)
        self.assertIn('answer_b', results)
        self.assertIn('answer_c', results)

    def test_process_question_full_v2_routes_all_steps_through_components(self):
        """The legacy v2 pipeline keeps its shape while using components."""
        from apps.common.ai.components import (
            DeepSeekFinalReviewComponent,
            DeepSeekIndependentVerifierComponent,
            KnowledgeAnalysisComponent,
            ModeAAnswerComponent,
            ModeBAnswerComponent,
            ModeCAnswerComponent,
            QuestionProbeComponent,
            VisionExtractionComponent,
        )

        responses = {
            QuestionProbeComponent: {
                'subject': 'math',
                'normalized_text': '规范化题干',
                'topic_tags_top3': ['函数'],
            },
            KnowledgeAnalysisComponent: {
                'subject': 'math',
                'difficulty': 'L2',
                'knowledge_points': [{'module': '函数'}],
            },
            VisionExtractionComponent: {
                'figure_present': False,
                'entities': [],
            },
            ModeAAnswerComponent: {
                'mode': 'A',
                'steps': [
                    {'step': 1, 'content': '列式'},
                    {'step': 2, 'content': '求解'},
                    {'step': 3, 'content': '验算'},
                ],
                'final_answer': '5',
                'summary': '完成',
            },
            ModeBAnswerComponent: {
                'mode': 'B',
                'questions': [
                    {
                        'question': f'第{index}步应选择什么？',
                        'options': {'A': '2', 'B': '3', 'C': '4', 'D': '5'},
                        'correct_option': 'D',
                        'correct_answer': 'D',
                        'reference_answer': '5',
                        'analysis': '代入计算',
                        'explanation': '代入计算',
                    }
                    for index in range(1, 4)
                ],
                'final_answer': '5',
                'summary': '完成',
            },
            ModeCAnswerComponent: {
                'mode': 'C',
                'questions': [
                    {
                        'question': f'第{index}步如何思考？',
                        'reference_answer': '代入计算',
                        'key_points': ['函数求值'],
                        'followup_hint': '检查代入值',
                    }
                    for index in range(1, 4)
                ],
                'final_answer': '5',
                'summary': '完成',
            },
        }
        created_types = []
        mode_components = {
            'A': ModeAAnswerComponent,
            'B': ModeBAnswerComponent,
            'C': ModeCAnswerComponent,
        }

        def component_factory(component_type):
            created_types.append(component_type)
            component = MagicMock()
            if component_type is DeepSeekIndependentVerifierComponent:
                component.run.side_effect = lambda question: {
                    'independent_answer': '5',
                    'independent_reasoning_summary': '代入后结果为 5。',
                    'reference_answer_valid': True,
                    'reference_analysis_valid': None,
                    'reference_issues': [],
                    'key_facts': ['代入计算'],
                    'confidence': 0.95,
                    'mode_content': responses[
                        mode_components[question.metadata['target_mode']]
                    ],
                }
            elif component_type is DeepSeekFinalReviewComponent:
                component.run.side_effect = lambda question: {
                    'trusted_answer': '5',
                    'qwen_content_valid': True,
                    'candidate_issues': [],
                    'confidence': 0.95,
                    'mode_content': responses[
                        mode_components[question.metadata['target_mode']]
                    ],
                }
            else:
                component.run.return_value = responses[component_type]
            return component

        service = AIReviewService(component_factory=component_factory)
        self.question.answer = '5'
        self.question.question_type = 'calculation'
        self.question.save(update_fields=['answer', 'question_type'])
        image_urls = [
            'https://example.test/one.png',
            'https://example.test/two.png',
        ]
        with patch.object(
            service, '_get_question_image_urls', return_value=image_urls
        ):
            results = service.process_question_full_v2(self.question.id)

        self.assertEqual(
            created_types,
            [
                QuestionProbeComponent,
                KnowledgeAnalysisComponent,
                VisionExtractionComponent,
                ModeAAnswerComponent,
                DeepSeekIndependentVerifierComponent,
                ModeBAnswerComponent,
                DeepSeekFinalReviewComponent,
                ModeCAnswerComponent,
                DeepSeekFinalReviewComponent,
            ],
        )
        self.assertEqual(
            set(results),
            {
                'probe', 'knowledge', 'vision', 'answer_a', 'answer_b',
                'answer_c', 'verifier', 'errors', 'image_count',
            },
        )
        self.assertEqual(results['image_count'], 2)
        self.assertEqual(results['errors'], {})
        self.assertEqual(results['answer_a']['mode'], 'A')
        self.assertEqual(results['answer_b']['mode'], 'B')
        self.assertEqual(results['answer_c']['mode'], 'C')
        self.assertEqual(results['verifier']['independent_answer'], '5')

        self.question.refresh_from_db()
        self.assertEqual(self.question.ai_processing_status, 'success')
        self.assertIsNotNone(self.question.ai_processed_at)

    def test_process_question_full_v2_normalizes_mixed_probe_tokens_and_saves(self):
        """Tight slash+whitespace boundaries reach v2 and persistence cleanly."""
        from apps.common.ai.components import (
            DeepSeekFinalReviewComponent,
            DeepSeekIndependentVerifierComponent,
            KnowledgeAnalysisComponent,
            ModeAAnswerComponent,
            ModeBAnswerComponent,
            ModeCAnswerComponent,
            QuestionProbeComponent,
            ResultVerifierComponent,
            VisionExtractionComponent,
        )
        from apps.common.ai.prompt_registry import PromptRegistry
        from apps.common.ai.types import AIResult

        class _ProbeResponseClient:
            def complete(
                self, task_key, *, system, user, images=(), trace_id=None
            ):
                probe_payload = {
                    'subject': 'math',
                    'question_type': '\u200b\\t\n\f\r\u3000',
                    'question_style': '__RAW_QUESTION_STYLE__',
                    'difficulty': '__RAW_DIFFICULTY__',
                    'difficulty_est': 'L4',
                    'knowledge_points': ['方程'],
                    'multi_part': False,
                    'proof_or_calc': 'calc',
                    'visual_risk_score': 0,
                    'reasoning_risk_score': 20,
                    'recommended_route': 'STANDARD',
                    'brief_reason': '基础计算',
                    'normalized_text': '解方程 x+1=2',
                }
                content = json.dumps(probe_payload, ensure_ascii=False)
                question_style_source = (
                    '\\' * 2 + 't' + 'calculation' + '\\' * 3 + 'n'
                )
                difficulty_source = (
                    '\\' * 2 + 'f' + 'L2' + '\\' * 3 + 'r'
                )
                content = content.replace(
                    '"__RAW_QUESTION_STYLE__"',
                    f'"{question_style_source}"',
                )
                content = content.replace(
                    '"__RAW_DIFFICULTY__"', f'"{difficulty_source}"'
                )
                return AIResult(
                    content=content,
                    provider='qwen',
                    model='configured-model',
                    latency_ms=1,
                    raw_response={},
                )

        responses = {
            KnowledgeAnalysisComponent: {'knowledge_points': []},
            VisionExtractionComponent: {'figure_present': False},
            ModeAAnswerComponent: {
                'mode': 'A',
                'steps': [
                    {'step': 1, 'content': '列式'},
                    {'step': 2, 'content': '求解'},
                    {'step': 3, 'content': '验算'},
                ],
                'final_answer': '2',
                'summary': '完成',
            },
            ModeBAnswerComponent: {
                'mode': 'B',
                'questions': [
                    {
                        'question': f'第{index}步应选择什么？',
                        'options': {'A': '1', 'B': '2', 'C': '3', 'D': '4'},
                        'correct_option': 'B',
                        'correct_answer': 'B',
                        'reference_answer': '2',
                        'analysis': '两边减一',
                        'explanation': '两边减一',
                    }
                    for index in range(1, 4)
                ],
                'final_answer': '2',
                'summary': '完成',
            },
            ModeCAnswerComponent: {
                'mode': 'C',
                'questions': [
                    {
                        'question': f'第{index}步如何思考？',
                        'reference_answer': '两边减一',
                        'key_points': ['等式性质'],
                        'followup_hint': '保持等式成立',
                    }
                    for index in range(1, 4)
                ],
                'final_answer': '2',
                'summary': '完成',
            },
            ResultVerifierComponent: {'pass': True},
        }
        registry = PromptRegistry()
        mode_components = {
            'A': ModeAAnswerComponent,
            'B': ModeBAnswerComponent,
            'C': ModeCAnswerComponent,
        }

        def component_factory(component_type):
            if component_type is QuestionProbeComponent:
                return QuestionProbeComponent(_ProbeResponseClient(), registry)
            component = MagicMock()
            if component_type is DeepSeekIndependentVerifierComponent:
                component.run.side_effect = lambda question: {
                    'independent_answer': '2',
                    'independent_reasoning_summary': '方程的解为 2。',
                    'reference_answer_valid': True,
                    'reference_analysis_valid': None,
                    'reference_issues': [],
                    'key_facts': ['两边减一'],
                    'confidence': 0.95,
                    'mode_content': responses[
                        mode_components[question.metadata['target_mode']]
                    ],
                }
            elif component_type is DeepSeekFinalReviewComponent:
                component.run.side_effect = lambda question: {
                    'trusted_answer': '2',
                    'qwen_content_valid': True,
                    'candidate_issues': [],
                    'confidence': 0.95,
                    'mode_content': responses[
                        mode_components[question.metadata['target_mode']]
                    ],
                }
            else:
                component.run.return_value = responses[component_type]
            return component

        service = AIReviewService(component_factory=component_factory)
        self.question.answer = '2'
        self.question.question_type = 'calculation'
        self.question.save(update_fields=['answer', 'question_type'])
        with patch.object(service, '_get_question_image_urls', return_value=[]):
            results = service.process_question_full_v2(self.question.id)

        self.assertEqual(results['errors'], {})
        self.assertEqual(results['probe']['question_type'], 'calculation')
        self.assertEqual(results['probe']['question_style'], 'calculation')
        self.assertEqual(results['probe']['difficulty'], 'L2')
        self.assertEqual(results['probe']['difficulty_est'], 'L2')

        service.save_results_to_question(self.question.id, results)
        self.question.refresh_from_db()
        self.assertEqual(self.question.ai_processing_status, 'success')
        self.assertEqual(
            self.question.ai_probe_result['question_type'], 'calculation'
        )
        self.assertEqual(
            self.question.ai_probe_result['question_style'], 'calculation'
        )
        self.assertEqual(self.question.ai_probe_result['difficulty'], 'L2')
        self.assertEqual(self.question.ai_probe_result['difficulty_est'], 'L2')

    def test_process_question_full_v2_marks_failed_for_invalid_mode_b_answer(self):
        """A malformed real Mode B component result must persist failed state."""
        from apps.common.ai.components import QuestionComponentFactory
        from apps.common.ai.prompt_registry import PromptRegistry
        from apps.common.ai.types import AIResult

        responses = {
            'question_probe': {
                'subject': 'math',
                'question_type': 'calculation',
                'grade': '七年级',
                'semester': '上学期',
                'chapter': '第三章',
                'difficulty': 'L2',
                'knowledge_points': ['方程'],
                'multi_part': False,
                'proof_or_calc': 'calc',
                'visual_risk_score': 0,
                'reasoning_risk_score': 20,
                'recommended_route': 'STANDARD',
                'brief_reason': '基础计算',
                'normalized_text': '解方程 x+1=2',
            },
            'knowledge_analysis': {
                'subject': 'math',
                'difficulty': 'L2',
                'knowledge_points': [
                    {'module': '一元一次方程', 'reason': '直接求解方程'}
                ],
            },
            'vision_fact_extract': {
                'subject': 'math',
                'figure_present': False,
                'figure_type': '',
                'visual_summary': '无图形',
                'diagram_facts': [],
                'text_marks_in_figure': [],
                'variables_and_symbols': [],
                'target_related_visual_info': [],
                'unclear_parts': [],
                'ocr_conflicts': [],
                'confidence': 'high',
            },
            'mode_a_answer': {
                'mode': 'A',
                'steps': [
                    {'step': 1, 'content': '列式'},
                    {'step': 2, 'content': '求解'},
                    {'step': 3, 'content': '验算'},
                ],
                'final_answer': '2',
                'summary': '完成',
            },
            'mode_b_answer': {
                'mode': 'B',
                'questions': [
                    {
                        'question': '下一步是什么？',
                        'options': {'A': '1', 'B': '2', 'C': '3', 'D': '4'},
                        'reference_answer': '数值2',
                        'analysis': '两边减一',
                    }
                ] * 3,
                'final_answer': '2',
                'summary': '递进引导',
            },
            'mode_c_answer': {
                'mode': 'C',
                'questions': [
                    {
                        'question': '等式两边如何变化？',
                        'reference_answer': '两边同时减一',
                        'key_points': ['等式性质'],
                        'followup_hint': '保持等式成立',
                    }
                ] * 3,
                'final_answer': '2',
                'summary': '开放引导',
            },
            'result_verify': {
                'pass': True,
                'consistency': 'consistent',
                'fact_violation': False,
                'calc_suspect': False,
                'issues': [],
                'retry_needed': False,
                'retry_reason': '',
            },
            'deepseek_independent_verify': {
                'independent_answer': '2',
                'independent_reasoning_summary': '方程的解为 2。',
                'reference_answer_valid': True,
                'reference_analysis_valid': None,
                'reference_issues': [],
                'key_facts': ['两边减一'],
                'confidence': 0.95,
                'mode_content': {
                    'mode': 'A',
                    'steps': [
                        {'step': 1, 'content': '列式'},
                        {'step': 2, 'content': '求解'},
                        {'step': 3, 'content': '验算'},
                    ],
                    'final_answer': '2',
                    'summary': '完成',
                },
            },
            'deepseek_final_review': {
                'trusted_answer': '2',
                'qwen_content_valid': True,
                'candidate_issues': [],
                'confidence': 0.95,
                'mode_content': {
                    'mode': 'C',
                    'questions': [
                        {
                            'question': '等式两边如何变化？',
                            'reference_answer': '两边同时减一',
                            'key_points': ['等式性质'],
                            'followup_hint': '保持等式成立',
                        }
                    ] * 3,
                    'final_answer': '2',
                    'summary': '开放引导',
                },
            },
        }

        class _ConfiguredResponseClient:
            def complete(
                self, task_key, *, system, user, images=(), trace_id=None
            ):
                return AIResult(
                    content=json.dumps(responses[task_key], ensure_ascii=False),
                    provider='qwen',
                    model='configured-model',
                    latency_ms=1,
                    raw_response={},
                )

        component_factory = QuestionComponentFactory(
            _ConfiguredResponseClient(), PromptRegistry()
        )
        service = AIReviewService(component_factory=component_factory)
        self.question.answer = '2'
        self.question.question_type = 'calculation'
        self.question.save(update_fields=['answer', 'question_type'])
        with patch.object(service, '_get_question_image_urls', return_value=[]):
            results = service.process_question_full_v2(self.question.id)

        self.assertEqual(set(results['errors']), {'answer_b'})
        self.assertIn('error', results['answer_b'])
        self.assertEqual(results['answer_a']['final_answer'], '2')
        self.assertEqual(results['answer_c']['final_answer'], '2')
        self.question.refresh_from_db()
        self.assertEqual(self.question.ai_processing_status, 'failed')


class AIProcessingJobModelTest(TestCase):
    """Durable queue records enforce capacity and per-question de-duplication."""

    def setUp(self):
        self.teacher = UserAccount.objects.create(
            mobile='13900009001', display_name='Queue Teacher', role_type='teacher',
        )
        self.paper = ExamPaper.objects.create(title='Queue Paper', subject='physics')
        self.questions = [
            ExamQuestion.objects.create(
                paper=self.paper,
                stem=f'Queue question {index}',
                answer='A',
                question_type='single_choice',
            )
            for index in range(3)
        ]

    @override_settings(AI_QUEUE_CAPACITY=2)
    def test_job_creation_deduplicates_active_question_and_rejects_capacity_overflow(self):
        from apps.review.models import AIProcessingJob, AIQueueCapacityExceeded

        first = AIProcessingJob.create_for_questions(
            creator=self.teacher,
            question_ids=[self.questions[0].id, self.questions[1].id],
            source='batch',
            model=None,
        )

        self.assertEqual(first.accepted_count, 2)
        duplicate = AIProcessingJob.create_for_questions(
            creator=self.teacher,
            question_ids=[self.questions[0].id],
            source='batch',
            model=None,
        )
        self.assertEqual(duplicate.accepted_count, 0)
        self.assertEqual(duplicate.duplicate_question_ids, [str(self.questions[0].id)])

        with self.assertRaises(AIQueueCapacityExceeded):
            AIProcessingJob.create_for_questions(
                creator=self.teacher,
                question_ids=[self.questions[2].id],
                source='batch',
                model=None,
            )


class AIQueueSchedulerTest(TestCase):
    def test_redis_lease_pool_enforces_limit_and_owner_aware_release(self):
        from apps.review.ai_queue import RedisLeasePool

        pool = RedisLeasePool('test-question', limit=2, ttl_seconds=60)
        with patch.object(pool, '_eval', side_effect=[1, 1, 0, 0, 1, 0]) as eval_call:
            self.assertTrue(pool.acquire('first'))
            self.assertTrue(pool.acquire('second'))
            self.assertFalse(pool.acquire('third'))
            self.assertFalse(pool.release('old-first'))
            self.assertTrue(pool.release('first'))
            self.assertFalse(pool.release('first'))

        self.assertEqual(eval_call.call_count, 6)

    def test_fair_item_selection_gives_each_three_jobs_four_baseline_slots(self):
        from apps.review.ai_queue import select_fair_item_ids

        jobs = [
            ('job-a', [f'a-{n}' for n in range(10)]),
            ('job-b', [f'b-{n}' for n in range(10)]),
            ('job-c', [f'c-{n}' for n in range(10)]),
        ]

        selected = select_fair_item_ids(jobs, limit=16)

        self.assertEqual(len(selected), 16)
        self.assertEqual(sum(item.startswith('a-') for item in selected), 6)
        self.assertEqual(sum(item.startswith('b-') for item in selected), 5)
        self.assertEqual(sum(item.startswith('c-') for item in selected), 5)

    @override_settings(AI_QUEUE_CAPACITY=10)
    def test_reserve_queued_items_marks_fair_items_dispatched_and_skips_cancelled_job(self):
        from apps.review.models import AIProcessingJob, AIProcessingJobItem
        from apps.review.ai_queue import reserve_queued_item_ids

        teacher = UserAccount.objects.create(
            mobile='13900009002', display_name='Dispatch Teacher', role_type='teacher',
        )
        paper = ExamPaper.objects.create(title='Dispatch Queue Paper', subject='physics')
        questions = [
            ExamQuestion.objects.create(paper=paper, stem=f'Dispatch {i}', answer='A', question_type='single_choice')
            for i in range(4)
        ]
        job = AIProcessingJob.create_for_questions(
            creator=teacher, question_ids=[question.id for question in questions[:3]], source='batch', model=None,
        ).job
        cancelled = AIProcessingJob.create_for_questions(
            creator=teacher, question_ids=[questions[3].id], source='batch', model=None,
        ).job
        cancelled.cancel_requested = True
        cancelled.save(update_fields=['cancel_requested'])

        with patch('apps.review.ai_queue.RedisLeasePool.acquire', return_value=True):
            reserved = reserve_queued_item_ids(limit=3)

        self.assertEqual(len(reserved), 3)
        self.assertEqual(
            AIProcessingJobItem.objects.filter(job=job, status='dispatched').count(), 3,
        )
        self.assertEqual(
            AIProcessingJobItem.objects.filter(job=cancelled, status='queued').count(), 1,
        )


class AIQueueExecutionTaskTest(TestCase):
    def test_execute_item_runs_existing_full_pipeline_and_releases_lease(self):
        from apps.review.models import AIProcessingJob, AIProcessingJobItem
        from apps.review.tasks import execute_ai_job_item

        teacher = UserAccount.objects.create(mobile='13900009003', display_name='Task Teacher', role_type='teacher')
        paper = ExamPaper.objects.create(title='Task Paper', subject='physics')
        question = ExamQuestion.objects.create(paper=paper, stem='Task stem', answer='A', question_type='single_choice')
        item = AIProcessingJob.create_for_questions(
            creator=teacher, question_ids=[question.id], source='batch', model=None,
        ).job.items.get()
        item.status = AIProcessingJobItem.Status.DISPATCHED
        item.save(update_fields=['status'])

        with (
            patch('apps.review.tasks.AIReviewService.process_question_full_v2', return_value={'errors': {}}),
            patch('apps.review.tasks.AIReviewService.save_results_to_question'),
            patch('apps.review.ai_queue.RedisLeasePool.release', return_value=True) as release,
        ):
            result = execute_ai_job_item.run(str(item.id))

        item.refresh_from_db()
        self.assertEqual(result['status'], 'complete')
        self.assertEqual(item.status, AIProcessingJobItem.Status.SUCCEEDED)
        release.assert_called_once_with(str(item.id))


class AIQueueCeleryDispatchTest(TestCase):
    def test_dispatch_enqueues_reserved_item_on_ai_batch_queue(self):
        from apps.review.ai_queue import dispatch_queued_ai_items

        with (
            patch('apps.review.ai_queue.reserve_queued_item_ids', return_value=['item-1']),
            patch('apps.review.tasks.execute_ai_job_item.apply_async') as enqueue,
        ):
            dispatch_queued_ai_items(limit=1)

        enqueue.assert_called_once_with(args=('item-1',), queue='ai.batch')


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


class SingleModeDispatchTest(TestCase):
    """Manual A/B/C dispatch must be idempotent and owner-aware."""

    def _dispatch_module(self):
        try:
            from apps.review import ai_mode_dispatch
        except ModuleNotFoundError:
            self.fail('apps.review.ai_mode_dispatch is required')
        return ai_mode_dispatch

    def test_dispatch_first_call_uses_generated_id_and_4200_second_lock(self):
        dispatch = self._dispatch_module()
        task_uuid = '12345678-1234-5678-1234-567812345678'

        with (
            patch.object(dispatch.uuid, 'uuid4', return_value=task_uuid),
            patch.object(dispatch.cache, 'add', return_value=True) as cache_add,
            patch(
                'apps.review.tasks.single_mode_ai_process_question.apply_async'
            ) as apply_async,
        ):
            result = dispatch.dispatch_single_mode_ai_task(
                'question-1', 'b', 'qwen3-vl-plus'
            )

        self.assertEqual(
            result,
            dispatch.ModeTaskDispatch(
                task_id=task_uuid, status='pending', created=True
            ),
        )
        lock_value = cache_add.call_args.args[1]
        self.assertEqual(json.loads(lock_value)['task_id'], task_uuid)
        cache_add.assert_called_once_with(
            'ai-mode-lock:question-1:B', lock_value, timeout=4200
        )
        apply_async.assert_called_once_with(
            args=('question-1', 'B'),
            kwargs={'model': 'qwen3-vl-plus'},
            task_id=task_uuid,
        )

    def test_dispatch_duplicate_returns_stored_id_without_enqueue(self):
        dispatch = self._dispatch_module()
        owner = json.dumps({'task_id': 'existing-task'})

        with (
            patch.object(dispatch.cache, 'add', return_value=False),
            patch.object(dispatch.cache, 'get', return_value=owner),
            patch(
                'apps.review.tasks.single_mode_ai_process_question.apply_async'
            ) as apply_async,
        ):
            result = dispatch.dispatch_single_mode_ai_task(
                'question-2', 'A', None
            )

        self.assertEqual(result.task_id, 'existing-task')
        self.assertEqual(result.status, 'running')
        self.assertFalse(result.created)
        apply_async.assert_not_called()

    def test_enqueue_failure_releases_only_its_own_lock(self):
        dispatch = self._dispatch_module()
        task_uuid = 'new-task'

        with (
            patch.object(dispatch.uuid, 'uuid4', return_value=task_uuid),
            patch.object(dispatch.cache, 'add', return_value=True),
            patch.object(
                dispatch,
                'release_single_mode_ai_task_lock',
                return_value=True,
            ) as release_lock,
            patch(
                'apps.review.tasks.single_mode_ai_process_question.apply_async',
                side_effect=RuntimeError('broker unavailable'),
            ),
            self.assertRaisesRegex(RuntimeError, 'broker unavailable'),
        ):
            dispatch.dispatch_single_mode_ai_task('question-3', 'C', None)

        release_lock.assert_called_once_with('question-3', 'C', task_uuid)

    def _atomic_cache(self, owner_value, *, takeover_value=None):
        class Serializer:
            def dumps(self, value):
                return b'encoded:' + value.encode('utf-8')

        serializer = Serializer()
        redis_key = ':1:ai-mode-lock:question-atomic:A'

        class Client:
            def __init__(self):
                self.store = {redis_key: serializer.dumps(owner_value)}
                self.eval_calls = []

            def eval(self, script, key_count, key, expected):
                self.eval_calls.append((script, key_count, key, expected))
                if takeover_value is not None:
                    self.store[key] = serializer.dumps(takeover_value)
                if self.store.get(key) == expected:
                    del self.store[key]
                    return 1
                return 0

        client = Client()
        backend = MagicMock()
        backend.make_and_validate_key.side_effect = (
            lambda key: f':1:{key}'
        )
        backend._cache = MagicMock()
        backend._cache._serializer = serializer
        backend._cache.get_client.return_value = client
        return backend, client, redis_key

    def test_atomic_release_deletes_exact_owned_value_with_one_eval(self):
        dispatch = self._dispatch_module()
        owner = json.dumps({'task_id': 'owned'}, separators=(',', ':'))
        backend, client, redis_key = self._atomic_cache(owner)

        with patch.object(dispatch, 'cache', backend):
            released = dispatch.release_single_mode_ai_task_lock(
                'question-atomic', 'A', 'owned'
            )

        self.assertTrue(released)
        self.assertNotIn(redis_key, client.store)
        self.assertEqual(len(client.eval_calls), 1)
        _, key_count, key, expected = client.eval_calls[0]
        self.assertEqual(key_count, 1)
        self.assertEqual(key, redis_key)
        self.assertEqual(expected, b'encoded:' + owner.encode('utf-8'))
        backend.delete.assert_not_called()

    def test_atomic_release_cannot_delete_owner_that_took_over_before_eval(self):
        dispatch = self._dispatch_module()
        old_owner = json.dumps({'task_id': 'old'}, separators=(',', ':'))
        new_owner = json.dumps({'task_id': 'new'}, separators=(',', ':'))
        backend, client, redis_key = self._atomic_cache(
            old_owner, takeover_value=new_owner
        )

        with patch.object(dispatch, 'cache', backend):
            released = dispatch.release_single_mode_ai_task_lock(
                'question-atomic', 'A', 'old'
            )

        self.assertFalse(released)
        self.assertEqual(
            client.store[redis_key],
            backend._cache._serializer.dumps(new_owner),
        )
        self.assertEqual(len(client.eval_calls), 1)
        backend.delete.assert_not_called()

    def test_atomic_release_fails_closed_on_unsupported_cache_backend(self):
        dispatch = self._dispatch_module()
        backend = MagicMock()
        backend.make_and_validate_key.return_value = ':1:lock'
        backend._cache = object()

        with patch.object(dispatch, 'cache', backend):
            released = dispatch.release_single_mode_ai_task_lock(
                'question-atomic', 'A', 'old'
            )

        self.assertFalse(released)
        backend.delete.assert_not_called()

    def test_malformed_duplicate_owner_is_stable_and_never_deleted(self):
        dispatch = self._dispatch_module()

        with (
            patch.object(dispatch.cache, 'add', return_value=False),
            patch.object(dispatch.cache, 'get', return_value='not-json'),
            patch.object(dispatch.cache, 'delete') as cache_delete,
            patch(
                'apps.review.tasks.single_mode_ai_process_question.apply_async'
            ) as apply_async,
        ):
            first = dispatch.dispatch_single_mode_ai_task('question-4', 'A', None)
            second = dispatch.dispatch_single_mode_ai_task('question-4', 'a', None)

        self.assertEqual(first.task_id, second.task_id)
        self.assertFalse(first.created)
        cache_delete.assert_not_called()
        apply_async.assert_not_called()


class SingleModeDispatchViewTest(TestCase):
    def setUp(self):
        self.paper = ExamPaper.objects.create(title='Dispatch paper', subject='math')
        self.question = ExamQuestion.objects.create(
            paper=self.paper,
            stem='1 + 1 = ?',
            answer='2',
            question_type='calculation',
        )
        self.client = APIClient()
        self.teacher = UserAccount.objects.create(
            mobile='13900008201',
            display_name='Dispatch Teacher',
            role_type='teacher',
        )
        grant_user_role(self.teacher, 'teacher')
        access = generate_tokens(self.teacher, 'teacher')['access_token']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')

    def test_view_returns_dispatcher_envelope_and_duplicate_flag(self):
        from apps.review.ai_mode_dispatch import ModeTaskDispatch

        with patch(
            'apps.review.views.dispatch_single_mode_ai_task',
            return_value=ModeTaskDispatch(
                task_id='same-task', status='running', created=False
            ),
        ) as dispatch:
            response = self.client.post(
                reverse(
                    'ai-process-single-mode', args=[self.question.id, 'b']
                ),
                {'model': 'qwen3-vl-plus'},
                format='json',
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            'success': True,
            'data': {
                'task_id': 'same-task',
                'status': 'running',
                'mode': 'B',
                'deduplicated': True,
            },
        })
        dispatch.assert_called_once_with(
            str(self.question.id), 'B', 'qwen3-vl-plus'
        )

    def test_invalid_or_missing_target_never_dispatches(self):
        with patch(
            'apps.review.views.dispatch_single_mode_ai_task'
        ) as dispatch:
            invalid = self.client.post(
                reverse(
                    'ai-process-single-mode', args=[self.question.id, 'D']
                ),
                {},
                format='json',
            )
            missing = self.client.post(
                reverse(
                    'ai-process-single-mode', args=['12345678-1234-5678-1234-567812345678', 'A']
                ),
                {},
                format='json',
            )

        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(invalid.json()['code'], 4001)
        self.assertEqual(missing.status_code, 404)
        dispatch.assert_not_called()

    def test_unauthenticated_request_never_dispatches(self):
        anonymous_client = APIClient()
        with patch(
            'apps.review.views.dispatch_single_mode_ai_task'
        ) as dispatch:
            response = anonymous_client.post(
                reverse(
                    'ai-process-single-mode', args=[self.question.id, 'A']
                ),
                {},
                format='json',
            )

        self.assertEqual(response.status_code, 401)
        dispatch.assert_not_called()


class TeacherAIEndpointPermissionTest(TestCase):
    """Teacher AI endpoints must honor the independently authenticated role."""

    def setUp(self):
        self.paper = ExamPaper.objects.create(
            title='Teacher permission paper', subject='math'
        )
        self.question = ExamQuestion.objects.create(
            paper=self.paper,
            stem='1 + 1 = ?',
            answer='2',
            question_type='calculation',
        )

    def _client(self, *, legacy_role, active_role, grants):
        user = UserAccount.objects.create(
            mobile=f'139{UserAccount.objects.count():08d}',
            display_name=f'{active_role} session',
            role_type=legacy_role,
        )
        for role in grants:
            grant_user_role(user, role)
        access = generate_tokens(user, active_role)['access_token']
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')
        return client

    def _teacher_ai_requests(self, client):
        question_id = self.question.id
        return (
            client.post(reverse('ai-process-question', args=[question_id]), {}, format='json'),
            client.post(reverse('ai-process-probe', args=[question_id]), {}, format='json'),
            client.get(reverse('single-ai-task-status', args=['permission-task'])),
            client.post(
                reverse('ai-process-single-mode', args=[question_id, 'A']),
                {},
                format='json',
            ),
            client.post(
                reverse('ai-confirm-answer', args=[question_id, 'A']),
                {},
                format='json',
            ),
            client.patch(
                reverse('ai-update-answer', args=[question_id, 'A']),
                {'edited_content': {'final_answer': '2'}},
                format='json',
            ),
            client.post(
                reverse('ai-update-knowledge', args=[question_id]),
                {'knowledge_data': {'difficulty': 'L1'}},
                format='json',
            ),
            client.get(reverse('ai-question-status', args=[question_id])),
            client.post(
                reverse('batch-ai-process'),
                {'question_ids': [str(question_id)]},
                format='json',
            ),
            client.get(reverse('batch-task-status', args=['permission-task'])),
            client.post(reverse('batch-task-cancel', args=['permission-task']), {}, format='json'),
            client.get(reverse('ai-task-status', args=['permission-task'])),
        )

    def test_student_parent_and_admin_sessions_are_forbidden_before_side_effects(self):
        from apps.review.ai_mode_dispatch import ModeTaskDispatch

        with (
            patch(
                'apps.review.tasks.single_ai_process_question.delay',
                return_value=SimpleNamespace(id='full-task'),
            ) as full,
            patch(
                'apps.review.tasks.single_probe_ai_process_question.delay',
                return_value=SimpleNamespace(id='probe-task'),
            ) as probe,
            patch(
                'apps.review.views.dispatch_single_mode_ai_task',
                return_value=ModeTaskDispatch(
                    task_id='mode-task', status='pending', created=True
                ),
            ) as single_mode,
            patch('apps.review.views.confirm_ai_answer', return_value={}) as confirm,
            patch('apps.review.views.update_ai_answer', return_value={}) as update_answer,
            patch(
                'apps.review.views.update_knowledge_enrichment', return_value={}
            ) as update_knowledge,
            patch(
                'apps.review.views.batch_ai_process_questions.delay',
                return_value=SimpleNamespace(id='batch-task'),
            ) as batch,
            patch('apps.review.views.cache.set') as cache_set,
        ):
            for role in ('student', 'parent', 'admin'):
                with self.subTest(role=role):
                    client = self._client(
                        legacy_role=role,
                        active_role=role,
                        grants=(role,),
                    )
                    responses = self._teacher_ai_requests(client)
                    self.assertTrue(responses)
                    self.assertTrue(all(response.status_code == 403 for response in responses))

        for side_effect in (
            full, probe, single_mode, confirm, update_answer,
            update_knowledge, batch, cache_set,
        ):
            side_effect.assert_not_called()

    def test_teacher_session_retains_success_and_validation_behavior(self):
        teacher = self._client(
            legacy_role='teacher', active_role='teacher', grants=('teacher',)
        )
        task = SimpleNamespace(id='teacher-task')
        with patch(
            'apps.review.tasks.single_ai_process_question.delay', return_value=task
        ) as dispatch:
            success = teacher.post(
                reverse('ai-process-question', args=[self.question.id]),
                {},
                format='json',
            )
        invalid = teacher.post(
            reverse('ai-process-single-mode', args=[self.question.id, 'D']),
            {},
            format='json',
        )

        self.assertEqual(success.status_code, 200)
        self.assertEqual(success.json()['data']['task_id'], 'teacher-task')
        self.assertEqual(invalid.status_code, 400)
        dispatch.assert_called_once_with(str(self.question.id), model=None)

    def test_multi_role_account_requires_teacher_active_session(self):
        user = UserAccount.objects.create(
            mobile='13900008299',
            display_name='Admin Teacher',
            role_type='admin',
        )
        grant_user_role(user, 'admin')
        grant_user_role(user, 'teacher')
        task = SimpleNamespace(id='multi-role-task')

        with patch(
            'apps.review.tasks.single_ai_process_question.delay', return_value=task
        ) as dispatch:
            admin_client = APIClient()
            admin_access = generate_tokens(user, 'admin')['access_token']
            admin_client.credentials(HTTP_AUTHORIZATION=f'Bearer {admin_access}')
            denied = admin_client.post(
                reverse('ai-process-question', args=[self.question.id]),
                {},
                format='json',
            )

            teacher_client = APIClient()
            teacher_access = generate_tokens(user, 'teacher')['access_token']
            teacher_client.credentials(HTTP_AUTHORIZATION=f'Bearer {teacher_access}')
            allowed = teacher_client.post(
                reverse('ai-process-question', args=[self.question.id]),
                {},
                format='json',
            )

        self.assertEqual(denied.status_code, 403)
        self.assertEqual(allowed.status_code, 200)
        dispatch.assert_called_once_with(str(self.question.id), model=None)
