from apps.common.question_types import (
    CANONICAL_QUESTION_TYPES,
    QUESTION_TYPE_LABELS,
    normalize_question_type,
)


def test_canonical_types_are_exactly_eleven():
    assert set(CANONICAL_QUESTION_TYPES) == {
        'single_choice', 'multiple_choice', 'fill_blank', 'true_false',
        'short_answer', 'question_answer', 'proof', 'experiment',
        'computation', 'drawing', 'essay',
    }


def test_canonical_type_labels_are_human_readable_chinese():
    assert QUESTION_TYPE_LABELS == {
        'single_choice': '单选题',
        'multiple_choice': '多选题',
        'fill_blank': '填空题',
        'true_false': '判断题',
        'short_answer': '简答题',
        'question_answer': '问答题',
        'proof': '证明题',
        'experiment': '实验题',
        'computation': '计算题',
        'drawing': '作图题',
        'essay': '作文题',
    }
    assert all('�' not in label for label in QUESTION_TYPE_LABELS.values())


def test_alias_and_structure_normalization():
    assert normalize_question_type(
        '不定项选择题', stem='下列正确的是', options=['A', 'B'], answer='AB'
    ) == 'multiple_choice'
    assert normalize_question_type(
        '解答题', stem='计算电阻的阻值', options=[], answer=''
    ) == 'computation'
    assert normalize_question_type(
        '', stem='请作出光路图', options=[], answer=''
    ) == 'drawing'
