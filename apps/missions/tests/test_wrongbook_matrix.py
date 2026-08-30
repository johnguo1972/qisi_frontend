import pytest
from django.conf import settings
from rest_framework.test import APIClient

from apps.missions.models import (
    LearningMission, MissionLevel, MissionQuestionRel,
    TeacherWrongBookCell, TeacherWrongBookMatrix,
    WrongBookGenerationBatch,
)
from apps.wrongbook.models import WrongBookItem
from apps.institutions.models import ClassStudent
from apps.institutions.models import Class, ClassTeacher, Institution
from apps.accounts.models import UserAccount
from apps.accounts.roles import grant_user_role
from apps.accounts.services import generate_tokens
from apps.parser.models import ExamPaper, ExamQuestion


@pytest.mark.django_db
def test_matrix_mark_cancel_and_generate_publishes_personal_mission(
    db, monkeypatch, tmp_path,
):
    teacher_user = UserAccount.objects.create(
        role_type='teacher', mobile='13900000901', display_name='teacher',
        stages=['junior'], subject='math', password='x',
    )
    grant_user_role(teacher_user, 'teacher')
    student_user = UserAccount.objects.create(
        role_type='student', mobile='13900000902', display_name='student', password='x',
    )
    grant_user_role(student_user, 'student')
    institution = Institution.objects.create(institution_name='matrix-test', created_by=teacher_user)
    sample_class = Class.objects.create(
        institution=institution, creator_teacher=teacher_user, class_name='matrix-class',
    )
    ClassTeacher.objects.create(class_obj=sample_class, teacher=teacher_user, role='owner')
    monkeypatch.setattr(settings, 'MEDIA_ROOT', str(tmp_path))
    monkeypatch.setattr('apps.study.student_views._build_pdf', lambda *args: b'%PDF-test')
    ClassStudent.objects.create(class_obj=sample_class, student=student_user, join_type='manual', status='active')
    paper = ExamPaper.objects.create(title='source', subject='math', stage='junior', source_file_path='source.pdf')
    original = ExamQuestion.objects.create(
        paper=paper, question_no='1', question_type='single_choice', subject='math',
        stem='original', difficulty=3, knowledge_points=[{'id': 'k1'}],
    )
    candidate = ExamQuestion.objects.create(
        paper=paper, question_no='2', question_type='single_choice', subject='math',
        stem='candidate', difficulty=3, knowledge_points=[{'id': 'k1'}],
        review_status='reviewed', need_review=False,
    )
    question_ten = ExamQuestion.objects.create(
        paper=paper, question_no='10', question_type='single_choice', subject='math',
        stem='question ten', difficulty=3, knowledge_points=[{'id': 'k1'}],
        review_status='reviewed', need_review=False,
    )
    source = LearningMission.objects.create(
        creator_teacher_id=teacher_user, class_obj=sample_class, mission_name='source mission',
        status='published', assignment_mode='flat', end_at='2026-09-20T23:59:59+08:00',
    )
    level = MissionLevel.objects.create(mission=source, level_no=1, level_name='work', level_type='practice')
    # Deliberately persist the old/non-natural order.  The matrix must still
    # expose the same 1, 2, 10 order as the source assignment.
    MissionQuestionRel.objects.create(mission=source, level=level, question_id=candidate.id, sort_no=1)
    MissionQuestionRel.objects.create(mission=source, level=level, question_id=original.id, sort_no=2)
    MissionQuestionRel.objects.create(mission=source, level=level, question_id=question_ten.id, sort_no=3)

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {generate_tokens(teacher_user, 'teacher')['access_token']}")
    response = client.get(f'/api/v1/missions/{source.id}/wrongbook-matrix')
    assert response.status_code == 200
    matrix = response.data['data']
    assert len(matrix['students']) == 1
    assert [row['question_no'] for row in matrix['questions']] == ['1', '2', '10']

    student_id = str(student_user.id)
    question_id = str(original.id)
    response = client.patch(
        f'/api/v1/missions/{source.id}/wrongbook-matrix',
        {'version': matrix['version'], 'cells': [
            {'student_id': student_id, 'source_question_id': question_id, 'wrong': True},
        ]}, format='json',
    )
    assert response.status_code == 200
    marked = response.data['data']['matrix']
    assert WrongBookItem.objects.filter(student_user_id=student_user, question_id=original.id).exists()
    assert TeacherWrongBookCell.objects.filter(matrix_id=marked['matrix_id'], status='marked').exists()

    response = client.post(
        f'/api/v1/missions/{source.id}/wrongbook-matrix/generate',
        {'version': marked['version'], 'idempotency_key': 'matrix-test-1'}, format='json',
    )
    assert response.status_code == 201
    batch = WrongBookGenerationBatch.objects.get(id=response.data['data']['id'])
    from apps.missions.tasks import generate_wrongbook_batch_task
    generate_wrongbook_batch_task.run(str(batch.id))
    batch.refresh_from_db()
    assert batch.status == 'published'
    generated = LearningMission.objects.get(source_generation_batch_id=batch.id)
    assert generated.status == 'published'
    assert generated.mission_kind == 'wrongbook_personal'
    assert generated.source_type == 'teacher_matrix'
    assert MissionQuestionRel.objects.filter(mission=generated).count() == 3
    assert MissionQuestionRel.objects.filter(mission=generated, target_student_ids=[student_id]).count() == 3
    extra_candidate = ExamQuestion.objects.create(
        paper=paper, question_no='3', question_type='single_choice', subject='math',
        stem='AI candidate', difficulty=3, knowledge_points=[{'id': 'k1'}],
        review_status='reviewed', need_review=False,
    )
    recommendations = client.post(
        f'/api/v1/missions/{source.id}/wrongbook-matrix/generation/{batch.id}/recommendations',
        {'limit': 10}, format='json',
    )
    assert recommendations.status_code == 200
    recommendation_ids = [row['id'] for row in recommendations.data['data']]
    assert recommendation_ids
    confirmed = client.post(
        f'/api/v1/missions/{source.id}/wrongbook-matrix/generation/{batch.id}/recommendations/confirm',
        {'recommendation_ids': recommendation_ids[:1], 'idempotency_key': 'ai-confirm-1'}, format='json',
    )
    assert confirmed.status_code == 201
    ai_mission = LearningMission.objects.get(id=confirmed.data['data']['mission_id'])
    assert ai_mission.parent_mission_id == generated.id
    assert ai_mission.mission_name.endswith('-AI补充')
    assert MissionQuestionRel.objects.filter(mission=ai_mission, source_provider='ai').count() == 1
    nested = client.get(f'/api/v1/missions/{source.id}/wrongbook-matrix/generation/{batch.id}')
    assert nested.status_code == 200

    student_client = APIClient()
    student_client.credentials(HTTP_AUTHORIZATION=f"Bearer {generate_tokens(student_user, 'student')['access_token']}")
    student_detail = student_client.get(f'/api/v1/student/missions/{generated.id}')
    assert student_detail.status_code == 200
    assert student_detail.data['data']['levels'][0]['question_count'] == 3

    response = client.patch(
        f'/api/v1/missions/{source.id}/wrongbook-matrix',
        {'version': marked['version'], 'cells': [
            {'student_id': student_id, 'source_question_id': question_id, 'wrong': False},
        ]}, format='json',
    )
    assert response.status_code == 200
    assert TeacherWrongBookCell.objects.filter(status='cancelled').exists()
    assert WrongBookItem.objects.filter(student_user_id=student_user, question_id=original.id).exists()
