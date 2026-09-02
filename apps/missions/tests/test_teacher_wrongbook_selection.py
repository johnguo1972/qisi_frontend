import pytest
from rest_framework.test import APIClient

from apps.accounts.models import UserAccount
from apps.accounts.roles import grant_user_role
from apps.accounts.services import generate_tokens
from apps.institutions.models import Class, ClassStudent, ClassTeacher, Institution
from apps.missions.models import LearningMission, MissionLevel, MissionQuestionRel, WrongBookGenerationBatch
from apps.parser.models import ExamPaper, ExamQuestion
from apps.study.models import QuestionRelation


@pytest.mark.django_db
def test_teacher_generation_falls_back_to_grouped_manual_selection(monkeypatch, tmp_path, settings):
    settings.MEDIA_ROOT = str(tmp_path)
    teacher = UserAccount.objects.create(
        role_type='teacher', mobile='13900000911', display_name='teacher',
        stages=['junior'], subject='math', password='x',
    )
    grant_user_role(teacher, 'teacher')
    student = UserAccount.objects.create(
        role_type='student', mobile='13900000912', display_name='学生1', password='x',
    )
    grant_user_role(student, 'student')
    institution = Institution.objects.create(institution_name='teacher-selection', created_by=teacher)
    sample_class = Class.objects.create(institution=institution, creator_teacher=teacher, class_name='选择班')
    ClassTeacher.objects.create(class_obj=sample_class, teacher=teacher, role='owner')
    ClassStudent.objects.create(class_obj=sample_class, student=student, join_type='manual', status='active')
    paper = ExamPaper.objects.create(title='selection-paper', subject='math', stage='junior', source_file_path='selection.pdf')
    original = ExamQuestion.objects.create(
        paper=paper, question_no='1', question_type='single_choice', subject='math',
        stem='original', difficulty=3, knowledge_points=[{'id': 'k1'}],
    )
    candidates = [ExamQuestion.objects.create(
        paper=paper, question_no=str(number), question_type='single_choice', subject='math',
        stem=f'candidate-{number}', difficulty=3, knowledge_points=[{'id': 'k1'}],
        review_status='reviewed', need_review=False,
    ) for number in (2, 3, 4, 5)]
    QuestionRelation.create_for_questions(original, candidates[0], teacher)
    source = LearningMission.objects.create(
        creator_teacher_id=teacher, class_obj=sample_class, mission_name='selection-source',
        status='published', assignment_mode='flat', end_at='2026-09-20T23:59:59+08:00',
    )
    level = MissionLevel.objects.create(mission=source, level_no=1, level_name='作业', level_type='practice')
    MissionQuestionRel.objects.create(mission=source, level=level, question_id=original.id, sort_no=1)

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {generate_tokens(teacher, 'teacher')['access_token']}")
    matrix = client.get(f'/api/v1/missions/{source.id}/wrongbook-matrix').data['data']
    marked = client.patch(
        f'/api/v1/missions/{source.id}/wrongbook-matrix',
        {'version': matrix['version'], 'cells': [{
            'student_id': str(student.id), 'source_question_id': str(original.id), 'wrong': True,
        }]}, format='json',
    ).data['data']['matrix']
    generated = client.post(
        f'/api/v1/missions/{source.id}/wrongbook-matrix/teacher-generate',
        {'version': marked['version'], 'idempotency_key': 'teacher-selection-test'}, format='json',
    )
    assert generated.status_code == 201
    batch = WrongBookGenerationBatch.objects.get(id=generated.data['data']['id'])

    def fail_if_ai_is_called(*args, **kwargs):
        raise AssertionError('manual selection must not call AI recommendations')

    monkeypatch.setattr(
        'apps.missions.teacher_wrongbook_selection.batch_recommendations',
        fail_if_ai_is_called,
        raising=False,
    )

    from apps.missions.tasks import generate_teacher_wrongbook_batch_task
    generate_teacher_wrongbook_batch_task.run(str(batch.id))
    batch.refresh_from_db()
    assert batch.status == 'awaiting_selection'

    groups = client.get(
        f'/api/v1/missions/{source.id}/wrongbook-matrix/generation/{batch.id}/candidate-groups',
    )
    assert groups.status_code == 200
    assert len(groups.data['data']) == 1
    assert [candidate['candidate_question_id'] for candidate in groups.data['data'][0]['candidates']] == [str(candidates[0].id)]
    assert groups.data['data'][0]['candidates'][0]['provider'] == 'relation'

    selected = [item['candidate_question_id'] for item in groups.data['data'][0]['candidates']]
    confirmed = client.post(
        f'/api/v1/missions/{source.id}/wrongbook-matrix/generation/{batch.id}/candidate-groups/confirm',
        {'idempotency_key': 'teacher-selection-confirm', 'groups': [{
            'student_id': str(student.id),
            'source_wrong_book_item_id': groups.data['data'][0]['source_wrong_book_item_id'],
            'candidate_question_ids': selected,
        }]}, format='json',
    )
    assert confirmed.status_code == 201
    batch.refresh_from_db()
    assert batch.status == 'published'
    mission = LearningMission.objects.get(id=confirmed.data['data']['mission_id'])
    assert MissionQuestionRel.objects.filter(mission=mission, target_student_ids=[str(student.id)]).count() == 2


@pytest.mark.django_db
def test_teacher_selection_uses_criteria_candidates_and_next_page_has_no_duplicates(tmp_path, settings):
    settings.MEDIA_ROOT = str(tmp_path)
    teacher = UserAccount.objects.create(
        role_type='teacher', mobile='13900000921', display_name='criteria teacher',
        stages=['junior'], subject='math', password='x',
    )
    grant_user_role(teacher, 'teacher')
    student = UserAccount.objects.create(
        role_type='student', mobile='13900000922', display_name='criteria student', password='x',
    )
    grant_user_role(student, 'student')
    institution = Institution.objects.create(institution_name='criteria-selection', created_by=teacher)
    sample_class = Class.objects.create(institution=institution, creator_teacher=teacher, class_name='criteria class')
    ClassTeacher.objects.create(class_obj=sample_class, teacher=teacher, role='owner')
    ClassStudent.objects.create(class_obj=sample_class, student=student, join_type='manual', status='active')
    paper = ExamPaper.objects.create(title='criteria-paper', subject='math', stage='junior', source_file_path='criteria.pdf')
    original = ExamQuestion.objects.create(
        paper=paper, question_no='1', question_type='single_choice', subject='math',
        stem='original', difficulty=3.2, knowledge_points=[{'id': 'k1'}],
    )
    for number in range(2, 13):
        ExamQuestion.objects.create(
            paper=paper, question_no=str(number), question_type='single_choice', subject='math',
            stem=f'criteria-{number}', difficulty=3.4, knowledge_points=[{'id': 'k1'}],
            review_status='reviewed', need_review=False,
        )
    ExamQuestion.objects.create(
        paper=paper, question_no='outside-difficulty', question_type='single_choice', subject='math',
        stem='outside difficulty', difficulty=3.8, knowledge_points=[{'id': 'k1'}],
        review_status='reviewed', need_review=False,
    )
    source = LearningMission.objects.create(
        creator_teacher_id=teacher, class_obj=sample_class, mission_name='criteria-source',
        status='published', assignment_mode='flat', end_at='2026-09-20T23:59:59+08:00',
    )
    level = MissionLevel.objects.create(mission=source, level_no=1, level_name='assignment', level_type='practice')
    MissionQuestionRel.objects.create(mission=source, level=level, question_id=original.id, sort_no=1)

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {generate_tokens(teacher, 'teacher')['access_token']}")
    matrix = client.get(f'/api/v1/missions/{source.id}/wrongbook-matrix').data['data']
    marked = client.patch(
        f'/api/v1/missions/{source.id}/wrongbook-matrix',
        {'version': matrix['version'], 'cells': [{
            'student_id': str(student.id), 'source_question_id': str(original.id), 'wrong': True,
        }]}, format='json',
    ).data['data']['matrix']
    generated = client.post(
        f'/api/v1/missions/{source.id}/wrongbook-matrix/teacher-generate',
        {'version': marked['version'], 'idempotency_key': 'criteria-selection-test'}, format='json',
    )
    batch = WrongBookGenerationBatch.objects.get(id=generated.data['data']['id'])

    from apps.missions.tasks import generate_teacher_wrongbook_batch_task
    generate_teacher_wrongbook_batch_task.run(str(batch.id))

    groups = client.get(
        f'/api/v1/missions/{source.id}/wrongbook-matrix/generation/{batch.id}/candidate-groups',
    )
    assert groups.status_code == 200
    first_group = groups.data['data'][0]
    first_ids = [candidate['candidate_question_id'] for candidate in first_group['candidates']]
    assert len(first_ids) == 5
    assert {candidate['provider'] for candidate in first_group['candidates']} == {'criteria'}

    replacement = client.post(
        f'/api/v1/missions/{source.id}/wrongbook-matrix/generation/{batch.id}/candidate-groups/{first_group["item_id"]}/next',
        {'excluded_question_ids': first_ids},
        format='json',
    )
    assert replacement.status_code == 200
    replacement_ids = [candidate['candidate_question_id'] for candidate in replacement.data['data']['candidates']]
    assert len(replacement_ids) == 5
    assert not set(first_ids) & set(replacement_ids)
