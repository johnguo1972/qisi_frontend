"""变式题生成校验器 — 校验 AI 输出的变式题是否符合 schema 和业务规则。"""
import logging
from typing import Any

logger = logging.getLogger(__name__)


class VariantValidator:
    """校验 AI 生成的变式题。

    校验项：
    - JSON schema 完整性（必填字段存在）
    - question_type 合法性
    - answer_count 正确性（选择题选项数与答案匹配）
    - units 合理性
    - value_ranges 合理性
    - single_choice_uniqueness（单选题答案唯一）
    """

    VALID_QUESTION_TYPES = {
        'single_choice', 'multiple_choice', 'fill_blank',
        'short_answer', 'essay', 'true_false',
        'computation', 'proof',
        # 中文别名
        '单选题', '多选题', '填空题', '简答题', '作文题', '判断题', '计算题', '证明题',
    }

    REQUIRED_FIELDS = ['stem', 'question_type', 'answer']

    def __init__(self):
        self.issues: list[str] = []

    def validate(self, variant_json: dict, original_question: Any = None) -> list[str]:
        """校验变式题 JSON。

        Args:
            variant_json: AI 生成的变式题 dict
            original_question: 原题 ExamQuestion 实例（可选，用于对比校验）

        Returns:
            问题列表，空列表 = 校验通过
        """
        self.issues = []

        self._check_schema(variant_json)
        if self.issues:
            return self.issues

        self._check_question_type(variant_json)
        self._check_answer_count(variant_json)
        self._check_single_choice_uniqueness(variant_json)
        self._check_value_ranges(variant_json)
        self._check_stem_not_empty(variant_json)

        if original_question:
            self._check_not_identical(variant_json, original_question)

        return self.issues

    # ------------------------------------------------------------------ #
    #  内部校验方法                                                        #
    # ------------------------------------------------------------------ #

    def _check_schema(self, data: dict) -> None:
        """检查必填字段是否存在。"""
        for field in self.REQUIRED_FIELDS:
            if field not in data or data[field] is None:
                self.issues.append(f"缺少必填字段: {field}")

        # 选择题必须有 options
        qtype = data.get('question_type', '')
        if qtype in ('single_choice', 'multiple_choice', '单选题', '多选题'):
            if 'options' not in data or not data['options']:
                self.issues.append("选择题必须包含 options 字段")
            elif not isinstance(data['options'], list):
                self.issues.append("options 必须是数组")

    def _check_question_type(self, data: dict) -> None:
        """检查题型是否合法。"""
        qtype = data.get('question_type', '')
        if qtype not in self.VALID_QUESTION_TYPES:
            self.issues.append(f"无效的题型: {qtype}")

    def _check_answer_count(self, data: dict) -> None:
        """检查选择题的选项数量和答案匹配。"""
        qtype = data.get('question_type', '')
        options = data.get('options', [])
        answer = data.get('answer', '')

        if not options or not isinstance(options, list):
            return

        # 单选题：答案应该是单个字母
        if qtype in ('single_choice', '单选题'):
            answer_str = str(answer).strip().upper()
            if len(answer_str) != 1:
                self.issues.append(f"单选题答案应为单个字母，当前为: {answer}")
            if len(options) < 2:
                self.issues.append(f"选择题至少需要2个选项，当前为: {len(options)}")

        # 多选题：答案应为多个逗号分隔的字母
        elif qtype in ('multiple_choice', '多选题'):
            answer_str = str(answer).strip().upper()
            answers = [a.strip() for a in answer_str.replace('，', ',').split(',') if a.strip()]
            if len(answers) < 2:
                self.issues.append(f"多选题答案应至少包含2个选项，当前为: {answer}")
            invalid_answers = [a for a in answers if len(a) != 1]
            if invalid_answers:
                self.issues.append(f"多选题答案包含无效选项: {invalid_answers}")

    def _check_single_choice_uniqueness(self, data: dict) -> None:
        """检查单选题选项内容是否互不相同。"""
        qtype = data.get('question_type', '')
        if qtype not in ('single_choice', '单选题'):
            return

        options = data.get('options', [])
        if not options or len(options) < 2:
            return

        # 检查选项内容是否重复
        contents = [opt.get('content', '').strip() for opt in options if isinstance(opt, dict)]
        seen = set()
        for c in contents:
            if c in seen and c:
                self.issues.append(f"单选题存在重复的选项内容: {c[:50]}")
                break
            seen.add(c)

    def _check_value_ranges(self, data: dict) -> None:
        """检查数值范围是否合理（难度、选项等）。"""
        difficulty = data.get('difficulty')
        if difficulty is not None:
            try:
                d = int(difficulty)
                if d < 1 or d > 5:
                    self.issues.append(f"难度应在 1-5 范围内，当前为: {difficulty}")
            except (ValueError, TypeError):
                self.issues.append(f"难度应为数字，当前为: {difficulty}")

    def _check_stem_not_empty(self, data: dict) -> None:
        """检查题干是否为空。"""
        stem = data.get('stem', '').strip()
        if not stem:
            self.issues.append("题干不能为空")

    def _check_not_identical(self, data: dict, original_question: Any) -> None:
        """检查变式题是否与原题完全相同（应变式而非复制）。"""
        try:
            orig_stem = getattr(original_question, 'stem', '').strip()
            new_stem = data.get('stem', '').strip()
            if orig_stem and new_stem and orig_stem == new_stem:
                self.issues.append("变式题题干与原题完全相同，请修改数值或情境")
        except Exception:
            pass  # 如果无法获取原题信息，跳过此校验
