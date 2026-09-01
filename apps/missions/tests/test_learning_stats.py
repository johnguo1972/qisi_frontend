import pytest
from rest_framework.test import APIClient

from apps.accounts.models import UserAccount
from apps.accounts.roles import grant_user_role
from apps.accounts.services import generate_tokens
from apps.institutions.models import Class, ClassStudent, ClassTeacher, Institution
from apps.missions.models import LearningMission, MissionLevel, MissionQuestionRel
from apps.parser.models import ExamPaper, ExamQuestion
from apps.study.models import AnswerAttempt


@pytest.mark.django_db
def test_learning_stats_returns_ordered_dense_student_answer_matrix():
    teacher = UserAccount.objects.create(
        role_type='teacher', mobile='13900000801', display_name='教师',
        stages=['junior'], subject='math', password='x',
    )
    grant_user_role(teacher, 'teacher')
    student_one = UserAccount.objects.create(
        role_type='student', mobile='13900000802', display_name='学生一', password='x',
    )
    student_two = UserAccount.objects.create(
        role_type='student', mobile='13900000803', display_name='学生二', password='x',
    )
    grant_user_role(student_one, 'student')
    grant_user_role(student_two, 'student')

    institution = Institution.objects.create(institution_name='stats-test', created_by=teacher)
    sample_class = Class.objects.create(
        institution=institution, creator_teacher=teacher, class_name='统计班',
    )
    ClassTeacher.objects.create(class_obj=sample_class, teacher=teacher, role='owner')
    ClassStudent.objects.create(
        class_obj=sample_class, student=student_one, join_type='manual', status='active',
    )
    ClassStudent.objects.create(
        class_obj=sample_class, student=student_two, join_type='manual', status='active',
    )

    paper = ExamPaper.objects.create(
        title='stats-paper', subject='math', stage='junior', source_file_path='source.pdf',
    )
    question_ten = ExamQuestion.objects.create(
        paper=paper, question_no='10', question_type='single_choice', subject='math',
        stem='第十题', answer='B', difficulty=3,
    )
    question_two = ExamQuestion.objects.create(
        paper=paper, question_no='2', question_type='single_choice', subject='math',
        stem='第二题', answer='A', difficulty=3,
    )
    mission = LearningMission.objects.create(
        creator_teacher_id=teacher, class_obj=sample_class, mission_name='统计作业',
        status='published', assignment_mode='flat',
    )
    level = MissionLevel.objects.create(
        mission=mission, level_no=1, level_name='作业题目', level_type='practice',
    )
    # Persist a non-natural relation order. The response must use question
    # number order and expose one display_no used by both matrix and list.
    MissionQuestionRel.objects.create(
        mission=mission, level=level, question_id=question_ten.id, sort_no=1,
    )
    MissionQuestionRel.objects.create(
        mission=mission, level=level, question_id=question_two.id, sort_no=2,
    )

    AnswerAttempt.objects.create(
        student_user_id=student_one, mission=mission, level=level,
        question_id=question_ten.id, attempt_no=1, answer_content={'selected_options': ['A']},
        is_correct=False, score=0,
    )
    AnswerAttempt.objects.create(
        student_user_id=student_one, mission=mission, level=level,
        question_id=question_ten.id, attempt_no=2, answer_content={'selected_options': ['B']},
        is_correct=True, score=5,
    )
    AnswerAttempt.objects.create(
        student_user_id=student_two, mission=mission, level=level,
        question_id=question_two.id, attempt_no=1, answer_content={'text': '待老师批改'},
        is_subjective_pending=True, score=0,
    )

    client = APIClient()
    token = generate_tokens(teacher, 'teacher')['access_token']
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
    response = client.get(f'/api/v1/missions/{mission.id}/learning-stats/')

    assert response.status_code == 200
    payload = response.data['data']
    assert [(item['display_no'], item['question_no']) for item in payload['questions']] == [
        (1, '2'), (2, '10'),
    ]
    assert [item['student_name'] for item in payload['students']] == ['学生一', '学生二']
    first, second = payload['students']
    first_by_question = {cell['display_no']: cell for cell in first['cells']}
    second_by_question = {cell['display_no']: cell for cell in second['cells']}
    assert first_by_question[2]['status'] == 'correct'
    assert first_by_question[2]['answer_text'] == 'B'
    assert second_by_question[1]['status'] == 'pending'
    assert second_by_question[2]['status'] == 'unanswered'
    assert payload['summary']['correct'] == 1
    assert payload['summary']['pending'] == 1
    assert payload['summary']['unanswered'] == 2

    newer_mission = LearningMission.objects.create(
        creator_teacher_id=teacher, class_obj=sample_class, mission_name='更新作业',
        status='published', assignment_mode='flat',
    )
    newer_level = MissionLevel.objects.create(
        mission=newer_mission, level_no=1, level_name='作业题目', level_type='practice',
    )
    MissionQuestionRel.objects.create(
        mission=newer_mission, level=newer_level, question_id=question_two.id, sort_no=1,
    )
    overview_response = client.get(f'/api/v1/classes/{sample_class.id}/learning-stats')
    assert overview_response.status_code == 200
    overview = overview_response.data['data']
    assert overview['mission_count'] == 2
    assert [row['mission_id'] for row in overview['missions']] == [
        str(newer_mission.id), str(mission.id),
    ]
    assert overview['missions'][0]['students'][0]['answered_count'] == 0
    assert overview['missions'][1]['students'][0]['correct_count'] == 1
    assert overview['missions'][1]['expected_answer_count'] == 4
