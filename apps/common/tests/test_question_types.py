from apps.common.question_types import CANONICAL_QUESTION_TYPES, normalize_question_type


def test_canonical_types_are_exactly_eleven():
    assert set(CANONICAL_QUESTION_TYPES) == {
        'single_choice', 'multiple_choice', 'fill_blank', 'true_false',
        'short_answer', 'question_answer', 'proof', 'experiment',
        'computation', 'drawing', 'essay',
    }


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
