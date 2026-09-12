import pytest
from rest_framework.test import APIClient

from apps.accounts.models import UserAccount
from apps.accounts.roles import grant_user_role
from apps.accounts.services import generate_tokens
from apps.institutions.models import Class, ClassStudent, ClassTeacher, Institution
from apps.missions.models import LearningMission, MissionLevel, MissionQuestionRel
from apps.parser.models import ExamPaper, ExamQuestion
from apps.study.models import AnswerAttempt


def authenticate_as(client, user, role='teacher'):
    grant_user_role(user, role)
    token = generate_tokens(user, role)['access_token']
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')


@pytest.fixture
def student_stats_fixture():
    teacher = UserAccount.objects.create(
        role_type='teacher', mobile='13900000901', display_name='Stats Teacher',
        subject='math', password='x',
    )
    student = UserAccount.objects.create(
        role_type='student', mobile='13900000902', display_name='Stats Student',
        password='x',
    )
    institution = Institution.objects.create(
        institution_name='student-stats-test', created_by=teacher,
    )
    sample_class = Class.objects.create(
        institution=institution, creator_teacher=teacher, class_name='Stats Class',
    )
    ClassTeacher.objects.create(class_obj=sample_class, teacher=teacher, role='owner')
    ClassStudent.objects.create(
        class_obj=sample_class, student=student, join_type='manual', status='active',
    )
    paper = ExamPaper.objects.create(
        title='student-stats-paper', subject='math', stage='junior',
        source_file_path='source.pdf',
    )
    question = ExamQuestion.objects.create(
        paper=paper, question_no='1', question_type='single_choice', subject='math',
        stem='Which answer is correct?', answer='B', difficulty=3,
        knowledge_points=[{'id': '999999', 'module': 'Linear functions'}],
    )
    pending_question = ExamQuestion.objects.create(
        paper=paper, question_no='2', question_type='essay', subject='math',
        stem='Explain the result.', answer='', difficulty=3,
    )
    mission = LearningMission.objects.create(
        creator_teacher_id=teacher, class_obj=sample_class, mission_name='History Mission',
        status='published', assignment_mode='flat',
    )
    level = MissionLevel.objects.create(
        mission=mission, level_no=1, level_name='Practice', level_type='practice',
    )
    MissionQuestionRel.objects.create(
        mission=mission, level=level, question_id=question.id, sort_no=1,
    )
    MissionQuestionRel.objects.create(
        mission=mission, level=level, question_id=pending_question.id, sort_no=2,
    )
    AnswerAttempt.objects.create(
        student_user_id=student, mission=mission, level=level,
        question_id=question.id, attempt_no=1,
        answer_content={'selected_options': ['A']}, is_correct=False, score=0,
    )
    AnswerAttempt.objects.create(
        student_user_id=student, mission=mission, level=level,
        question_id=question.id, attempt_no=2,
        answer_content={'selected_options': ['B']}, is_correct=True, score=5,
    )
    AnswerAttempt.objects.create(
        student_user_id=student, mission=mission, level=level,
        question_id=question.id, attempt_no=3,
        answer_content={'selected_options': ['C']}, is_correct=False, score=0,
        submit_source='draft',
    )
    AnswerAttempt.objects.create(
        student_user_id=student, mission=mission, level=level,
        question_id=pending_question.id, attempt_no=1,
        answer_content={'text': 'Needs teacher review'}, is_subjective_pending=True,
    )
    return teacher, student, sample_class, mission, question


@pytest.mark.django_db
def test_teacher_can_view_student_history_and_knowledge_graph(student_stats_fixture):
    teacher, student, sample_class, mission, question = student_stats_fixture
    client = APIClient()
    authenticate_as(client, teacher)

    response = client.get(
        f'/api/v1/classes/{sample_class.id}/students/{student.id}/learning-stats',
        {'page': 1, 'page_size': 20},
    )

    assert response.status_code == 200
    payload = response.data['data']
    assert response.data['meta'] == {'page': 1, 'page_size': 20, 'total': 1}
    assert payload['student']['id'] == str(student.id)
    assert payload['summary']['mission_count'] == 1
    assert payload['summary']['attempt_count'] == 3
    assert payload['summary']['answered_question_count'] == 2
    assert payload['summary']['correct_count'] == 1
    assert payload['summary']['wrong_count'] == 0
    assert payload['summary']['pending_count'] == 1

    mission_row = payload['missions'][0]
    question_row = next(row for row in mission_row['questions'] if row['question_id'] == str(question.id))
    assert mission_row['mission_id'] == str(mission.id)
    assert mission_row['question_count'] == 2
    assert question_row['status'] == 'correct'
    assert question_row['latest_attempt']['attempt_no'] == 2
    assert len(question_row['attempt_history']) == 2
    assert question_row['attempt_history'][0]['attempt_no'] == 2
    assert question_row['attempt_history'][1]['attempt_no'] == 1
    pending_row = next(row for row in mission_row['questions'] if row['question_id'] != str(question.id))
    assert pending_row['status'] == 'pending'
    assert pending_row['attempt_history'][0]['is_subjective_pending'] is True

    graph = payload['knowledge_graph']
    assert graph['metric_version'] == 'latest_question_attempt_v1'
    assert graph['items'][0]['attempt'] == 2
    assert graph['items'][0]['correct'] == 1
    assert graph['items'][0]['mastery'] == 'mastered'
    assert graph['tree'][0]['children'][0]['children'][0]['children'][0]['type'] == 'knowledge'

    slash_response = client.get(
        f'/api/v1/classes/{sample_class.id}/students/{student.id}/learning-stats/',
    )
    assert slash_response.status_code == 200


@pytest.mark.django_db
def test_teacher_cannot_view_student_outside_owned_class(student_stats_fixture):
    _, student, sample_class, _, _ = student_stats_fixture
    outsider = UserAccount.objects.create(
        role_type='teacher', mobile='13900000903', display_name='Outsider', password='x',
    )
    client = APIClient()
    authenticate_as(client, outsider)

    response = client.get(
        f'/api/v1/classes/{sample_class.id}/students/{student.id}/learning-stats',
    )

    assert response.status_code == 403
