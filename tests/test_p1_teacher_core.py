import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_teacher_can_create_one_mission_for_multiple_classes(teacher_client, teacher_user, sample_institution, sample_class):
    from apps.institutions.models import Class, ClassTeacher
    second = Class.objects.create(
        institution=sample_institution, creator_teacher=teacher_user, class_name='第二班级',
    )
    ClassTeacher.objects.create(class_obj=second, teacher=teacher_user, role='owner')
    response = teacher_client.post('/api/v1/missions/', {
        'mission_name': '多班级作业', 'class_ids': [str(sample_class.id), str(second.id)],
    }, format='json')
    assert response.status_code == 201, response.json()
    detail = teacher_client.get(f"/api/v1/missions/{response.json()['data']['id']}/").json()['data']
    assert set(detail['class_ids']) == {str(sample_class.id), str(second.id)}
    assert detail['assignment_mode'] == 'flat'
    assert detail['start_at']


@pytest.mark.django_db
@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
def test_student_import_is_partial_and_returns_error_rows(teacher_client, sample_class):
    content = '姓名,手机号,班级标识\n张三,13800000001,%s\n错误手机号,123,%s\n张三,13800000001,%s\n' % (
        sample_class.class_no, sample_class.class_no, sample_class.class_no,
    )
    upload = SimpleUploadedFile('students.csv', content.encode('utf-8'), content_type='text/csv')
    response = teacher_client.post(
        f'/api/v1/classes/{sample_class.id}/students/import', {'file': upload}, format='multipart',
    )
    assert response.status_code == 200, response.json()
    data = response.json()['data']
    assert data['status'] == 'partially_succeeded'
    assert data['success_count'] == 1
    assert data['failed_count'] == 2
    errors = teacher_client.get(f"/api/v1/student-imports/{data['id']}/errors").json()['data']['items']
    assert [item['row_no'] for item in errors] == [3, 4]


@pytest.mark.django_db
def test_mission_progress_exposes_p1_status_breakdown(teacher_client, teacher_user, sample_class, student_user, sample_question):
    from apps.institutions.models import ClassStudent
    from apps.missions.models import LearningMission, MissionLevel, MissionQuestionRel
    from apps.study.models import StudentMissionProgress

    ClassStudent.objects.create(class_obj=sample_class, student=student_user, join_type='manual', status='active')
    mission = LearningMission.objects.create(
        mission_name='进度作业', status='published', creator_teacher_id=teacher_user, class_obj=sample_class,
    )
    level = MissionLevel.objects.create(mission=mission, level_no=1, level_name='题目', level_type='practice')
    MissionQuestionRel.objects.create(mission=mission, level=level, question_id=sample_question.id, sort_no=1)
    StudentMissionProgress.objects.create(mission=mission, student_user_id=student_user)
    response = teacher_client.get(f'/api/v1/missions/{mission.id}/progress')
    assert response.status_code == 200, response.json()
    data = response.json()['data']
    assert data['summary']['not_started'] == 1
    assert data['students'][0]['status'] == 'not_started'


@pytest.mark.django_db
def test_student_submit_is_idempotent_and_full_submit_locks_mission(student_client, teacher_user, sample_class, student_user, sample_question):
    from apps.institutions.models import ClassStudent
    from apps.missions.models import LearningMission, MissionLevel, MissionQuestionRel
    from apps.study.models import StudentMissionProgress, AnswerAttempt

    ClassStudent.objects.create(class_obj=sample_class, student=student_user, join_type='manual', status='active')
    mission = LearningMission.objects.create(
        mission_name='提交作业', status='published', creator_teacher_id=teacher_user, class_obj=sample_class,
    )
    level = MissionLevel.objects.create(mission=mission, level_no=1, level_name='题目', level_type='practice')
    MissionQuestionRel.objects.create(mission=mission, level=level, question_id=sample_question.id, sort_no=1)
    StudentMissionProgress.objects.create(mission=mission, student_user_id=student_user)
    payload = {
        'question_id': str(sample_question.id), 'mission_id': str(mission.id),
        'level_id': str(level.id), 'answer_content': {'selected_options': ['A']},
        'idempotency_key': 'p1-submit-1',
    }
    first = student_client.post('/api/v1/student/attempts', payload, format='json')
    second = student_client.post('/api/v1/student/attempts', payload, format='json')
    assert first.status_code == second.status_code == 200
    assert second.json()['data']['idempotent_replay'] is True
    assert AnswerAttempt.objects.filter(mission=mission, student_user_id=student_user).count() == 1
    final = student_client.post(f'/api/v1/student/missions/{mission.id}/submit')
    assert final.status_code == 200, final.json()
    assert final.json()['data']['status'] == 'graded'


@pytest.mark.django_db
def test_mission_progress_can_be_filtered_by_assigned_class(teacher_client, teacher_user, sample_institution, sample_class, student_user, sample_question):
    from apps.institutions.models import Class, ClassStudent, ClassTeacher
    from apps.missions.models import LearningMission, MissionClassAssignment, MissionLevel, MissionQuestionRel

    second_class = Class.objects.create(
        institution=sample_institution, creator_teacher=teacher_user, class_name='二班',
    )
    ClassTeacher.objects.create(class_obj=second_class, teacher=teacher_user, role='owner')
    second_student = type(student_user).objects.create(
        role_type='student', mobile='13900000004', display_name='李四', status='active',
    )
    ClassStudent.objects.create(class_obj=sample_class, student=student_user, join_type='manual', status='active')
    ClassStudent.objects.create(class_obj=second_class, student=second_student, join_type='manual', status='active')
    mission = LearningMission.objects.create(
        mission_name='多班级进度', status='published', creator_teacher_id=teacher_user, class_obj=sample_class,
    )
    MissionClassAssignment.objects.create(mission=mission, class_obj=sample_class)
    MissionClassAssignment.objects.create(mission=mission, class_obj=second_class)
    level = MissionLevel.objects.create(mission=mission, level_no=1, level_name='题目', level_type='practice')
    MissionQuestionRel.objects.create(mission=mission, level=level, question_id=sample_question.id, sort_no=1)

    all_rows = teacher_client.get(f'/api/v1/missions/{mission.id}/progress').json()['data']
    filtered = teacher_client.get(
        f'/api/v1/missions/{mission.id}/progress?class_id={second_class.id}',
    ).json()['data']
    assert all_rows['summary']['total'] == 2
    assert filtered['class_id'] == str(second_class.id)
    assert filtered['summary']['total'] == 1
    assert filtered['students'][0]['student_id'] == str(second_student.id)


@pytest.mark.django_db
@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
def test_student_import_accepts_student_no_without_mobile(teacher_client, sample_class):
    from apps.accounts.models import UserAccount

    content = '姓名,学号,班级标识\n王五,S2026001,%s\n' % sample_class.class_no
    upload = SimpleUploadedFile('students-by-no.csv', content.encode('utf-8'), content_type='text/csv')
    response = teacher_client.post(
        f'/api/v1/classes/{sample_class.id}/students/import', {'file': upload}, format='multipart',
    )
    assert response.status_code == 200, response.json()
    data = response.json()['data']
    assert data['status'] == 'succeeded'
    student = UserAccount.objects.get(student_no='S2026001')
    assert student.mobile is None
    assert student.display_name == '王五'


@pytest.mark.django_db
def test_student_import_dispatches_background_task(teacher_client, sample_class, monkeypatch):
    dispatched = []
    monkeypatch.setattr(
        'apps.institutions.tasks.process_student_import.delay',
        lambda task_id, rows: dispatched.append((task_id, rows)),
    )
    content = '姓名,学号,班级标识\n赵六,S2026002,%s\n' % sample_class.class_no
    upload = SimpleUploadedFile('students-async.csv', content.encode('utf-8'), content_type='text/csv')
    response = teacher_client.post(
        f'/api/v1/classes/{sample_class.id}/students/import', {'file': upload}, format='multipart',
    )
    assert response.status_code == 202, response.json()
    data = response.json()['data']
    assert data['status'] == 'validating'
    assert dispatched and dispatched[0][0] == data['id']
    assert dispatched[0][1][0]['student_no'] == 'S2026002'


@pytest.mark.django_db
def test_subjective_grading_updates_student_mission_progress(teacher_client, teacher_user, sample_class, student_user, sample_question):
    from apps.institutions.models import ClassStudent
    from apps.missions.models import LearningMission, MissionLevel, MissionQuestionRel
    from apps.study.models import AnswerAttempt, StudentMissionProgress

    ClassStudent.objects.create(class_obj=sample_class, student=student_user, join_type='manual', status='active')
    mission = LearningMission.objects.create(
        mission_name='主观题作业', status='published', creator_teacher_id=teacher_user, class_obj=sample_class,
    )
    level = MissionLevel.objects.create(mission=mission, level_no=1, level_name='主观题', level_type='practice')
    MissionQuestionRel.objects.create(mission=mission, level=level, question_id=sample_question.id, sort_no=1)
    progress = StudentMissionProgress.objects.create(
        mission=mission, student_user_id=student_user, progress_status='submitted', progress_percent=100,
    )
    attempt = AnswerAttempt.objects.create(
        mission=mission, level=level, student_user_id=student_user, question_id=sample_question.id,
        answer_content={'answer': '作答'}, is_subjective_pending=True, submit_source='manual',
    )
    response = teacher_client.patch(
        f'/api/v1/missions/{mission.id}/grading/attempts/{attempt.id}/',
        {'score': 88, 'feedback': '完成良好'}, format='json',
    )
    assert response.status_code == 200, response.json()
    progress.refresh_from_db()
    assert progress.progress_status == 'graded'
    assert float(progress.progress_percent) == 100


@pytest.mark.django_db
def test_mission_rejects_class_outside_teacher_grade_scope(teacher_client, teacher_user, sample_class):
    sample_class.grade_level = '一年级'
    sample_class.save(update_fields=['grade_level', 'updated_at'])
    response = teacher_client.post('/api/v1/missions/', {
        'mission_name': '范围校验作业', 'class_ids': [str(sample_class.id)],
    }, format='json')
    assert response.status_code == 403
    assert '年级' in response.json()['message']


@pytest.mark.django_db
def test_targeted_mission_is_hidden_from_other_class_students(
    teacher_client, student_client, teacher_user, sample_class, student_user,
):
    from apps.accounts.models import UserAccount
    from apps.accounts.roles import grant_user_role
    from apps.institutions.models import ClassStudent
    from apps.missions.models import LearningMission, MissionClassAssignment
    from apps.accounts.services import generate_tokens

    other_student = UserAccount.objects.create(
        role_type='student', mobile='13900000005', display_name='非目标学生', status='active',
    )
    grant_user_role(other_student, 'student')
    ClassStudent.objects.create(class_obj=sample_class, student=student_user, join_type='manual', status='active')
    ClassStudent.objects.create(class_obj=sample_class, student=other_student, join_type='manual', status='active')
    mission = LearningMission.objects.create(
        mission_name='专属学生作业', status='published', creator_teacher_id=teacher_user,
        class_obj=sample_class, target_student_ids=[str(student_user.id)],
    )
    MissionClassAssignment.objects.create(
        mission=mission, class_obj=sample_class,
        target_student_ids=[str(student_user.id)],
    )
    other_client = APIClient()
    other_client.credentials(HTTP_AUTHORIZATION=f"Bearer {generate_tokens(other_student, 'student')['access_token']}")

    allowed_home = student_client.get('/api/v1/student/home').json()['data']['missions']
    blocked_home = other_client.get('/api/v1/student/home').json()['data']['missions']
    assert any(str(item['mission']['id']) == str(mission.id) for item in allowed_home)
    assert not any(str(item['mission']['id']) == str(mission.id) for item in blocked_home)
    assert other_client.get(f'/api/v1/student/missions/{mission.id}').status_code == 403


@pytest.mark.django_db
def test_related_questions_require_submitted_source_and_keep_assigned_candidates(
    student_client, teacher_user, sample_class, student_user, sample_paper, sample_question,
):
    from apps.institutions.models import ClassStudent
    from apps.missions.models import LearningMission, MissionLevel, MissionQuestionRel
    from apps.study.models import AnswerAttempt, StudentMissionProgress
    from apps.parser.models import ExamQuestion

    ClassStudent.objects.create(class_obj=sample_class, student=student_user, join_type='manual', status='active')
    candidate = ExamQuestion.objects.create(
        paper=sample_paper, question_no='2', question_type='single_choice', subject='数学',
        stem='关联题', answer='A', difficulty=2,
    )
    mission = LearningMission.objects.create(
        mission_name='关联题作业', status='published', creator_teacher_id=teacher_user,
        class_obj=sample_class,
    )
    level = MissionLevel.objects.create(mission=mission, level_no=1, level_name='题目', level_type='practice')
    MissionQuestionRel.objects.create(mission=mission, level=level, question_id=candidate.id, sort_no=1)
    StudentMissionProgress.objects.create(mission=mission, student_user_id=student_user)

    before = student_client.get(f'/api/v1/student/questions/{sample_question.id}/related')
    assert before.status_code == 403
    AnswerAttempt.objects.create(
        student_user_id=student_user, question_id=sample_question.id,
        answer_content={'selected_options': ['A']}, submit_source='manual',
    )
    after = student_client.get(f'/api/v1/student/questions/{sample_question.id}/related')
    assert after.status_code == 200
    assert any(str(item['id']) == str(candidate.id) for item in after.json()['data'])


@pytest.mark.django_db
def test_mission_statistics_route_is_compatible_with_progress(teacher_client, teacher_user, sample_class):
    from apps.missions.models import LearningMission

    mission = LearningMission.objects.create(
        mission_name='统计接口作业', status='published', creator_teacher_id=teacher_user,
        class_obj=sample_class,
    )
    progress = teacher_client.get(f'/api/v1/missions/{mission.id}/progress').json()
    statistics = teacher_client.get(f'/api/v1/missions/{mission.id}/statistics').json()
    assert progress['data']['summary'] == statistics['data']['summary']


@pytest.mark.django_db
@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
def test_student_import_all_failed_and_reimport_is_idempotent(teacher_client, sample_class):
    invalid = SimpleUploadedFile(
        'invalid.csv', '姓名,手机号\n坏数据,123\n坏数据2,124\n'.encode('utf-8'), content_type='text/csv',
    )
    failed = teacher_client.post(
        f'/api/v1/classes/{sample_class.id}/students/import', {'file': invalid}, format='multipart',
    )
    assert failed.status_code == 200
    assert failed.json()['data']['status'] == 'failed'
    assert failed.json()['data']['success_count'] == 0
    assert failed.json()['data']['failed_count'] == 2

    def upload_once():
        return teacher_client.post(
            f'/api/v1/classes/{sample_class.id}/students/import',
            {'file': SimpleUploadedFile('same.csv', '姓名,手机号\n张三,13800000006\n'.encode('utf-8'), content_type='text/csv')},
            format='multipart',
        )

    first = upload_once()
    second = upload_once()
    assert first.json()['data']['status'] == second.json()['data']['status'] == 'succeeded'
    from apps.accounts.models import UserAccount
    from apps.institutions.models import ClassStudent
    student = UserAccount.objects.get(mobile='13800000006')
    assert ClassStudent.objects.filter(class_obj=sample_class, student=student, status='active').count() == 1


@pytest.mark.django_db
def test_student_cannot_import_into_teacher_class(student_client, sample_class):
    upload = SimpleUploadedFile(
        'students.csv', '姓名,手机号\n学生,13800000007\n'.encode('utf-8'), content_type='text/csv',
    )
    response = student_client.post(
        f'/api/v1/classes/{sample_class.id}/students/import', {'file': upload}, format='multipart',
    )
    assert response.status_code == 403


@pytest.mark.django_db
def test_student_import_worker_rechecks_teacher_permission(teacher_user, sample_class):
    from apps.institutions.models import ClassTeacher, StudentImportTask
    from apps.institutions.tasks import process_student_import

    task = StudentImportTask.objects.create(
        institution=sample_class.institution, class_obj=sample_class,
        uploaded_by=teacher_user, file_path='student-imports/test.csv',
        status='validating', total_count=1,
    )
    ClassTeacher.objects.filter(class_obj=sample_class, teacher=teacher_user).delete()
    result = process_student_import(str(task.id), [{'name': '不应导入', 'mobile': '13800000008'}])
    task.refresh_from_db()
    assert result['status'] == 'failed'
    assert task.status == 'failed'
