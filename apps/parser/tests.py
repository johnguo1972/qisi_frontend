"""Tests for parser app services."""
import json
from django.test import TestCase
from apps.common.utils import repair_json_string
from apps.parser.services.schema_service import validate_and_repair_json
from apps.parser.services.postprocess_service import (
    normalize_question_type, separate_answer_fields,
    validate_images, postprocess_questions
)
from apps.parser.services.formula_service import validate_latex, check_formula_need_review
from apps.parser.services.merge_service import merge_cross_page_questions


class JSONRepairTest(TestCase):
    def test_repair_markdown_block(self):
        raw = '```json\n{"page_no": 1, "questions": []}\n```'
        result = repair_json_string(raw)
        self.assertIn('"page_no"', result)
        self.assertNotIn('```', result)

    def test_repair_trailing_comma(self):
        raw = '{"page_no": 1, "questions": [],}'
        result = repair_json_string(raw)
        data = json.loads(result)
        self.assertEqual(data['page_no'], 1)

    def test_repair_chinese_quotes(self):
        raw = '{"stem": "这是一道“测试”题"}'
        result = repair_json_string(raw)
        data = json.loads(result)
        self.assertIn('测试', data['stem'])


class SchemaValidationTest(TestCase):
    def test_valid_page_parse(self):
        data = {
            "page_no": 1,
            "questions": [
                {
                    "question_no": "1",
                    "question_type": "single_choice",
                    "stem": "已知函数f(x)=x^2+1，则f(1)的值为",
                    "options": [
                        {"label": "A", "content": "1"},
                        {"label": "B", "content": "2"},
                        {"label": "C", "content": "3"},
                        {"label": "D", "content": "4"}
                    ],
                    "answer": "B",
                    "confidence": 0.95,
                    "images": [],
                    "knowledge_points": ["函数"],
                    "difficulty": 2,
                }
            ]
        }
        result = validate_and_repair_json(json.dumps(data))
        self.assertEqual(len(result['questions']), 1)
        self.assertEqual(result['questions'][0]['question_no'], '1')

    def test_invalid_question_type_fallback(self):
        data = {
            "page_no": 1,
            "questions": [{
                "question_no": "1",
                "question_type": "invalid_type",
                "stem": "test",
            }]
        }
        result = validate_and_repair_json(json.dumps(data))
        self.assertEqual(result['questions'][0]['question_type'], 'unknown')


class FormulaValidationTest(TestCase):
    def test_valid_latex(self):
        text = "已知 $f(x) = x^2 + 1$，求 $f(1)$"
        valid, errors = validate_latex(text)
        self.assertTrue(valid)

    def test_unbalanced_dollar(self):
        text = "已知 $f(x) = x^2"
        valid, errors = validate_latex(text)
        self.assertFalse(valid)
        self.assertTrue(len(errors) > 0)

    def test_unbalanced_braces(self):
        text = "已知 $\\frac{1}{2}$ and $\\frac{1{2}$"
        valid, errors = validate_latex(text)
        self.assertFalse(valid)

    def test_formula_need_review(self):
        self.assertTrue(check_formula_need_review("已知 $f(x) = x^2"))
        self.assertFalse(check_formula_need_review("正常文本"))
        self.assertFalse(check_formula_need_review(""))


class MergeServiceTest(TestCase):
    def test_no_cross_page(self):
        pages = [
            {"page_no": 1, "questions": [{"question_no": "1", "stem": "Q1"}]},
            {"page_no": 2, "questions": [{"question_no": "2", "stem": "Q2"}]},
        ]
        result = merge_cross_page_questions(pages)
        self.assertEqual(len(result), 2)

    def test_cross_page_same_question_no(self):
        pages = [
            {
                "page_no": 1,
                "questions": [{
                    "question_no": "1",
                    "stem": "阅读材料，",
                    "page_end": 2,
                }]
            },
            {
                "page_no": 2,
                "questions": [{
                    "question_no": "1",
                    "stem": "续上文，回答问题。",
                }]
            },
        ]
        result = merge_cross_page_questions(pages)
        self.assertEqual(len(result), 1)
        self.assertIn('阅读材料', result[0]['stem'])
        self.assertIn('回答问题', result[0]['stem'])

    def test_cross_page_different_question_no(self):
        """Different question_no on next page should NOT be merged."""
        pages = [
            {
                "page_no": 1,
                "questions": [{
                    "question_no": "1",
                    "stem": "Q1",
                    "page_end": 2,
                }]
            },
            {
                "page_no": 2,
                "questions": [{
                    "question_no": "2",
                    "stem": "Q2",
                }]
            },
        ]
        result = merge_cross_page_questions(pages)
        self.assertEqual(len(result), 2)


class PostprocessTest(TestCase):
    def test_normalize_type_single_choice(self):
        self.assertEqual(normalize_question_type('一、选择题', 'unknown'), 'single_choice')

    def test_normalize_type_multiple_choice(self):
        self.assertEqual(normalize_question_type('二、多项选择题', 'unknown'), 'multiple_choice')

    def test_normalize_type_fill_blank(self):
        self.assertEqual(normalize_question_type('三、填空题', 'unknown'), 'fill_blank')

    def test_normalize_type_keyword(self):
        self.assertEqual(normalize_question_type('多项选择题', 'unknown'), 'multiple_choice')

    def test_separate_answers(self):
        q = {'stem': '已知函数f(x)=x^2。【答案】f(x)在x=0处取最小值。【解析】求导即可。'}
        result = separate_answer_fields(q)
        self.assertEqual(result['answer'], 'f(x)在x=0处取最小值。')
        self.assertNotIn('【答案】', result['stem'])

    def test_validate_images_missing(self):
        q = {'stem': '如图所示的几何体', 'images': [], 'need_review_reason': ''}
        self.assertFalse(validate_images(q))
        self.assertIn('图片', q['need_review_reason'])

    def test_full_pipeline(self):
        pages = [
            {
                "page_no": 1,
                "questions": [
                    {
                        "question_no": "1",
                        "question_type": "unknown",
                        "section_title": "一、选择题",
                        "stem": "1. 已知函数 $f(x)=x^2$，则 $f(2)$ 等于",
                        "options": [
                            {"label": "A", "content": "2"},
                            {"label": "B", "content": "4"},
                            {"label": "C", "content": "6"},
                            {"label": "D", "content": "8"}
                        ],
                        "answer": "",
                        "analysis": "",
                        "images": [],
                        "confidence": 0.9,
                    }
                ]
            }
        ]
        result = postprocess_questions(pages)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['question_type'], 'single_choice')
        self.assertEqual(result[0]['need_review'], False)
