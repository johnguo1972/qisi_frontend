"""Tests for VariantValidator."""
import json
from django.test import TestCase

from apps.courses.validator import VariantValidator


class TestVariantValidatorSchema(TestCase):
    """Test JSON schema validation."""

    def setUp(self):
        self.validator = VariantValidator()

    def test_valid_single_choice(self):
        """Valid single choice question should pass."""
        data = {
            'stem': '若 x + 2 = 5，则 x = ?',
            'question_type': 'single_choice',
            'answer': 'B',
            'options': [
                {'label': 'A', 'content': '2'},
                {'label': 'B', 'content': '3'},
                {'label': 'C', 'content': '4'},
                {'label': 'D', 'content': '5'},
            ],
            'difficulty': 2,
        }
        issues = self.validator.validate(data)
        self.assertEqual(issues, [])

    def test_missing_stem(self):
        """Missing stem field should fail."""
        data = {
            'question_type': 'single_choice',
            'answer': 'A',
        }
        issues = self.validator.validate(data)
        self.assertTrue(any('stem' in issue for issue in issues))

    def test_missing_question_type(self):
        """Missing question_type field should fail."""
        data = {
            'stem': 'Some question',
            'answer': 'A',
        }
        issues = self.validator.validate(data)
        self.assertTrue(any('question_type' in issue for issue in issues))

    def test_missing_answer(self):
        """Missing answer field should fail."""
        data = {
            'stem': 'Some question',
            'question_type': 'single_choice',
        }
        issues = self.validator.validate(data)
        self.assertTrue(any('answer' in issue for issue in issues))

    def test_choice_missing_options(self):
        """选择题没有 options 应该失败."""
        data = {
            'stem': 'Some question',
            'question_type': 'single_choice',
            'answer': 'A',
        }
        issues = self.validator.validate(data)
        self.assertTrue(any('options' in issue for issue in issues))


class TestVariantValidatorQuestionType(TestCase):
    """Test question_type validation."""

    def setUp(self):
        self.validator = VariantValidator()

    def test_valid_types(self):
        """Valid question types should pass."""
        for qtype in ['single_choice', 'multiple_choice', 'fill_blank', 'computation', '单选题', '多选题', '填空题', '计算题']:
            data = {
                'stem': 'Test question',
                'question_type': qtype,
                'answer': 'A' if 'choice' in qtype else '3',
            }
            issues = self.validator.validate(data)
            type_issues = [i for i in issues if '题型' in i or 'question_type' in i]
            self.assertEqual(type_issues, [], f"Failed for {qtype}: {type_issues}")

    def test_invalid_type(self):
        """Invalid question_type should fail."""
        data = {
            'stem': 'Test',
            'question_type': 'invalid_type_xyz',
            'answer': 'A',
        }
        issues = self.validator.validate(data)
        self.assertTrue(any('无效' in i for i in issues))


class TestVariantValidatorAnswerCount(TestCase):
    """Test answer count validation."""

    def setUp(self):
        self.validator = VariantValidator()

    def test_single_choice_multi_letter_answer(self):
        """单选题答案为多个字母应该失败."""
        data = {
            'stem': 'Test',
            'question_type': 'single_choice',
            'answer': 'A,B',
            'options': [
                {'label': 'A', 'content': 'Option A'},
                {'label': 'B', 'content': 'Option B'},
            ],
        }
        issues = self.validator.validate(data)
        self.assertTrue(any('单个字母' in i for i in issues))

    def test_single_choice_valid_answer(self):
        """单选题答案为单个字母应该通过."""
        data = {
            'stem': 'Test',
            'question_type': 'single_choice',
            'answer': 'B',
            'options': [
                {'label': 'A', 'content': 'Option A'},
                {'label': 'B', 'content': 'Option B'},
            ],
        }
        issues = self.validator.validate(data)
        answer_issues = [i for i in issues if '答案' in i]
        self.assertEqual(answer_issues, [])

    def test_multiple_choice_single_answer(self):
        """多选题答案为单个选项应该失败."""
        data = {
            'stem': 'Test',
            'question_type': 'multiple_choice',
            'answer': 'A',
            'options': [
                {'label': 'A', 'content': 'Option A'},
                {'label': 'B', 'content': 'Option B'},
                {'label': 'C', 'content': 'Option C'},
            ],
        }
        issues = self.validator.validate(data)
        self.assertTrue(any('至少包含2个' in i for i in issues))

    def test_multiple_choice_valid_answer(self):
        """多选题答案为多个字母应该通过."""
        data = {
            'stem': 'Test',
            'question_type': 'multiple_choice',
            'answer': 'A,C',
            'options': [
                {'label': 'A', 'content': 'Option A'},
                {'label': 'B', 'content': 'Option B'},
                {'label': 'C', 'content': 'Option C'},
            ],
        }
        issues = self.validator.validate(data)
        answer_issues = [i for i in issues if '答案' in i]
        self.assertEqual(answer_issues, [])

    def test_too_few_options(self):
        """选择题只有1个选项应该失败."""
        data = {
            'stem': 'Test',
            'question_type': 'single_choice',
            'answer': 'A',
            'options': [
                {'label': 'A', 'content': 'Only option'},
            ],
        }
        issues = self.validator.validate(data)
        self.assertTrue(any('至少需要2个' in i for i in issues))


class TestVariantValidatorSingleChoiceUniqueness(TestCase):
    """Test single choice option uniqueness."""

    def setUp(self):
        self.validator = VariantValidator()

    def test_duplicate_options(self):
        """单选题选项内容重复应该失败."""
        data = {
            'stem': 'Test',
            'question_type': 'single_choice',
            'answer': 'A',
            'options': [
                {'label': 'A', 'content': 'Same content'},
                {'label': 'B', 'content': 'Same content'},
                {'label': 'C', 'content': 'Different'},
                {'label': 'D', 'content': 'Also different'},
            ],
        }
        issues = self.validator.validate(data)
        self.assertTrue(any('重复' in i for i in issues))

    def test_unique_options(self):
        """单选题选项内容唯一应该通过."""
        data = {
            'stem': 'Test',
            'question_type': 'single_choice',
            'answer': 'A',
            'options': [
                {'label': 'A', 'content': 'Option A'},
                {'label': 'B', 'content': 'Option B'},
                {'label': 'C', 'content': 'Option C'},
                {'label': 'D', 'content': 'Option D'},
            ],
        }
        issues = self.validator.validate(data)
        dup_issues = [i for i in issues if '重复' in i]
        self.assertEqual(dup_issues, [])


class TestVariantValidatorValueRanges(TestCase):
    """Test value range validation."""

    def setUp(self):
        self.validator = VariantValidator()

    def test_valid_difficulty(self):
        """Valid difficulty (1-5) should pass."""
        for d in [1, 2, 3, 4, 5]:
            data = {
                'stem': 'Test',
                'question_type': 'fill_blank',
                'answer': '42',
                'difficulty': d,
            }
            issues = self.validator.validate(data)
            diff_issues = [i for i in issues if '难度' in i]
            self.assertEqual(diff_issues, [], f"Failed for difficulty={d}: {diff_issues}")

    def test_invalid_difficulty_too_high(self):
        """Difficulty > 5 should fail."""
        data = {
            'stem': 'Test',
            'question_type': 'fill_blank',
            'answer': '42',
            'difficulty': 6,
        }
        issues = self.validator.validate(data)
        self.assertTrue(any('难度' in i for i in issues))

    def test_invalid_difficulty_too_low(self):
        """Difficulty < 1 should fail."""
        data = {
            'stem': 'Test',
            'question_type': 'fill_blank',
            'answer': '42',
            'difficulty': 0,
        }
        issues = self.validator.validate(data)
        self.assertTrue(any('难度' in i for i in issues))


class TestVariantValidatorStemEmpty(TestCase):
    """Test stem not empty validation."""

    def setUp(self):
        self.validator = VariantValidator()

    def test_empty_stem(self):
        """Empty stem should fail."""
        data = {
            'stem': '',
            'question_type': 'fill_blank',
            'answer': '42',
        }
        issues = self.validator.validate(data)
        self.assertTrue(any('题干' in i for i in issues))

    def test_whitespace_stem(self):
        """Whitespace-only stem should fail."""
        data = {
            'stem': '   ',
            'question_type': 'fill_blank',
            'answer': '42',
        }
        issues = self.validator.validate(data)
        self.assertTrue(any('题干' in i for i in issues))


class TestVariantValidatorNotIdentical(TestCase):
    """Test variant not identical to original."""

    def setUp(self):
        self.validator = VariantValidator()

    def test_identical_stem(self):
        """Identical stem should fail."""
        data = {
            'stem': 'This is the original question text',
            'question_type': 'fill_blank',
            'answer': '42',
        }

        class FakeQuestion:
            stem = 'This is the original question text'

        issues = self.validator.validate(data, FakeQuestion())
        self.assertTrue(any('完全相同' in i for i in issues))

    def test_different_stem(self):
        """Different stem should pass."""
        data = {
            'stem': 'This is a different question',
            'question_type': 'fill_blank',
            'answer': '42',
        }

        class FakeQuestion:
            stem = 'This is the original question text'

        issues = self.validator.validate(data, FakeQuestion())
        identical_issues = [i for i in issues if '完全相同' in i]
        self.assertEqual(identical_issues, [])
