import pytest

from apps.missions.snapshots import snapshot_payload
from apps.papers.models import ExamPaper
from apps.parser.models import ExamQuestion, QuestionOption


@pytest.mark.django_db
def test_student_question_payload_includes_formula_ready_option_html():
    paper = ExamPaper.objects.create(
        title='formula-option-paper',
        subject='math',
        source_file_path='source.zip',
    )
    question = ExamQuestion.objects.create(
        paper=paper,
        question_no='3',
        question_type='single_choice',
        subject='math',
        stem='Formula option question',
    )
    QuestionOption.objects.create(
        question=question,
        option_label='A',
        content='raw [[formula:q003_formula_01]]',
        content_html='<img data-formula-key="q003_formula_01" src="/media/formula.png" />',
    )

    payload = snapshot_payload(question, relation=None)

    assert payload['options'][0]['content_html'] == (
        '<img data-formula-key="q003_formula_01" src="/media/formula.png" />'
    )
