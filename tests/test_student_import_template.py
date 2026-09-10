import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings


@pytest.mark.django_db
def test_student_import_template_matches_student_form(teacher_client, sample_class):
    response = teacher_client.get(
        f'/api/v1/classes/{sample_class.id}/students/import-template',
    )

    assert response.status_code == 200
    content = response.content.decode('utf-8-sig')
    assert '学生姓名(必填),学校(必填),年级(必填),班级(必填),班型(必填),学生手机号(必填),家长姓名,家长手机号' in content
    assert '学号' not in content
    assert sample_class.class_name in content


@pytest.mark.django_db
@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
def test_new_student_import_routes_rows_and_reports_unmatched_classes(
    teacher_client, teacher_user, sample_class,
):
    from apps.accounts.models import StudentParentBind, UserAccount
    from apps.institutions.models import Class, ClassStudent, ClassTeacher

    sample_class.grade_level = '八年级'
    sample_class.save(update_fields=['grade_level', 'updated_at'])
    second_class = Class.objects.create(
        institution=sample_class.institution,
        creator_teacher=teacher_user,
        class_name='八年级2班',
        grade_level='八年级',
    )
    ClassTeacher.objects.create(
        class_obj=second_class, teacher=teacher_user, role='owner',
    )
    content = (
        '学生姓名(必填),学校(必填),年级(必填),班级(必填),班型(必填),学生手机号(必填),家长姓名,家长手机号\n'
        f'张三,实验中学,八年级,{sample_class.class_name},A+班,13820000001,张三家长,13820000002\n'
        f'李四,实验中学,八年级,不存在的班级,S班,13820000003,,\n'
        f'王五,实验中学,八年级,{second_class.class_name},A班,13820000004,,\n'
    )
    upload = SimpleUploadedFile(
        'students-new.csv', content.encode('utf-8'), content_type='text/csv',
    )

    response = teacher_client.post(
        f'/api/v1/classes/{sample_class.id}/students/import',
        {'file': upload}, format='multipart',
    )

    assert response.status_code == 200, response.json()
    data = response.json()['data']
    assert data['status'] == 'partially_succeeded'
    assert data['success_count'] == 2
    assert data['failed_count'] == 1
    student_one = UserAccount.objects.get(mobile='13820000001')
    student_two = UserAccount.objects.get(mobile='13820000004')
    assert ClassStudent.objects.filter(
        class_obj=sample_class, student=student_one, status='active',
        grade_level='八年级', class_type='A_PLUS',
    ).exists()
    assert ClassStudent.objects.filter(
        class_obj=second_class, student=student_two, status='active',
        grade_level='八年级', class_type='A',
    ).exists()
    assert not UserAccount.objects.filter(mobile='13820000003').exists()
    assert StudentParentBind.objects.filter(
        student_user_id=student_one, parent_user_id__mobile='13820000002',
        bind_status='active', is_primary=True,
    ).exists()
    errors = teacher_client.get(
        f"/api/v1/student-imports/{data['id']}/errors",
    ).json()['data']['items']
    assert errors[0]['row_no'] == 3
    assert errors[0]['error_code'] == 'CLASS_NOT_FOUND'
