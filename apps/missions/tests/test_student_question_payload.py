import pytest

from apps.accounts.models import UserAccount
from apps.missions.models import LearningMission, MissionLevel, MissionQuestionRel
from apps.missions.snapshots import snapshot_payload
from apps.parser.models import ExamPaper, ExamQuestion, QuestionImage, QuestionOption


@pytest.mark.django_db
def test_student_question_payload_keeps_full_question_content_without_snapshot():
    teacher = UserAccount.objects.create(
        role_type='teacher', mobile='13900000901', display_name='payload teacher', password='x',
    )
    paper = ExamPaper.objects.create(
        title='student-payload-paper', subject='physics', source_file_path='source.pdf',
    )
    question = ExamQuestion.objects.create(
        paper=paper,
        question_no='1',
        question_type='true_false',
        subject='physics',
        stem='请判断下列说法是否正确。',
        subquestions=[
            {'label': '1', 'stem': '温度升高，分子运动更快。'},
            {'label': '2', 'stem': '$\\frac{1}{2}$ 是一个分数。'},
        ],
        tables=[{'rows': [['物理量', '数值'], ['温度', '20℃']]}],
    )
    QuestionOption.objects.create(question=question, option_label='A', content='选项内容', sort_order=1)
    QuestionImage.objects.create(
        paper=paper, question=question, image_type='diagram', file_path='questions/diagram.png',
        placement='stem', display_width=360, sort_order=1,
    )
    mission = LearningMission.objects.create(
        mission_name='student payload mission', creator_teacher_id=teacher,
    )
    level = MissionLevel.objects.create(mission=mission, level_no=1, level_name='第一关')
    relation = MissionQuestionRel.objects.create(
        mission=mission, level=level, question_id=question.id, sort_no=1,
    )

    payload = snapshot_payload(question, relation)

    assert payload['subquestions'] == question.subquestions
    assert payload['tables'] == question.tables
    assert payload['options'] == [{'label': 'A', 'content': '选项内容'}]
    assert payload['images'][0]['file_path'] == 'questions/diagram.png'


@pytest.mark.django_db
def test_student_question_payload_uses_source_structural_fields_for_legacy_partial_snapshot():
    teacher = UserAccount.objects.create(
        role_type='teacher', mobile='13900000902', display_name='legacy teacher', password='x',
    )
    paper = ExamPaper.objects.create(
        title='legacy-snapshot-paper', subject='physics', source_file_path='source.pdf',
    )
    question = ExamQuestion.objects.create(
        paper=paper, question_no='2', question_type='true_false', subject='physics',
        stem='当前题干', subquestions=[{'label': '1', 'stem': '子判断项'}],
        tables=[{'rows': [['列'], ['值']]}],
    )
    QuestionOption.objects.create(question=question, option_label='A', content='当前选项', sort_order=1)
    mission = LearningMission.objects.create(
        mission_name='legacy snapshot mission', creator_teacher_id=teacher,
    )
    level = MissionLevel.objects.create(mission=mission, level_no=1, level_name='第一关')
    relation = MissionQuestionRel.objects.create(
        mission=mission, level=level, question_id=question.id, sort_no=1,
        question_snapshot={'stem': '发布时题干'},
    )

    payload = snapshot_payload(question, relation)

    assert payload['stem'] == '发布时题干'
    assert payload['subquestions'] == question.subquestions
    assert payload['tables'] == question.tables
    assert payload['options'] == [{'label': 'A', 'content': '当前选项'}]
