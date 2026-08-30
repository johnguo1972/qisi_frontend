"""Background jobs for institution data imports."""
import csv
import io

from celery import shared_task
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import UserAccount
from apps.accounts.roles import has_user_role
from .models import ClassStudent, ClassTeacher, StudentImportTask, StudentImportRow


@shared_task(name='institutions.process_student_import')
def process_student_import(task_id, rows):
    """Process validated import rows outside the request/response cycle."""
    from . import import_views as importer

    task = StudentImportTask.objects.select_related(
        'class_obj', 'uploaded_by',
    ).get(pk=task_id)
    if (
        not task.uploaded_by
        or not has_user_role(task.uploaded_by, 'teacher')
        or not ClassTeacher.objects.filter(
            class_obj=task.class_obj, teacher=task.uploaded_by,
        ).exists()
    ):
        task.status = 'failed'
        task.completed_at = timezone.now()
        task.save(update_fields=['status', 'completed_at'])
        return {'task_id': str(task.id), 'status': task.status}
    try:
        seen = set()
        errors = []
        success = 0
        for row_no, data in enumerate(rows, start=2):
            raw = dict(data)
            mobile = data.get('mobile', '').replace(' ', '')
            student_no = data.get('student_no', '')
            name = data.get('name', '')
            error_code = ''
            error_message = ''
            student = None
            if not name or len(name) > 64:
                error_code, error_message = 'INVALID_NAME', '姓名不能为空且不能超过64个字符'
            elif not mobile and not student_no:
                error_code, error_message = 'MISSING_IDENTIFIER', '手机号和学号至少提供一个'
            elif mobile and not importer.PHONE_RE.match(mobile):
                error_code, error_message = 'INVALID_MOBILE', '手机号格式无效'
            elif len(student_no) > 64:
                error_code, error_message = 'INVALID_STUDENT_NO', '学号不能超过64个字符'
            elif data.get('class_identifier') and data['class_identifier'] not in (
                task.class_obj.class_name, task.class_obj.class_no, str(task.class_obj_id),
            ):
                error_code, error_message = 'CLASS_MISMATCH', '班级标识与目标班级不匹配'
            elif (mobile and f'mobile:{mobile}' in seen) or (student_no and f'student_no:{student_no}' in seen):
                error_code, error_message = 'DUPLICATE_ROW', '文件内匹配字段重复'
            else:
                if mobile:
                    seen.add(f'mobile:{mobile}')
                if student_no:
                    seen.add(f'student_no:{student_no}')
                mobile_student = UserAccount.objects.filter(mobile=mobile).first() if mobile else None
                student_no_matches = list(UserAccount.objects.filter(student_no=student_no).order_by('id')) if student_no else []
                if len(student_no_matches) > 1 and not mobile_student:
                    error_code, error_message = 'AMBIGUOUS_STUDENT_NO', '学号匹配到多个学生账号'
                else:
                    student = mobile_student or (student_no_matches[0] if student_no_matches else None)
                if student and not has_user_role(student, 'student'):
                    error_code, error_message = 'ROLE_CONFLICT', '匹配到的账号不是学生账号'
                elif student and student.status != 'active':
                    student.status = 'active'
                    student.save(update_fields=['status', 'updated_at'])
            if error_code:
                StudentImportRow.objects.create(
                    task=task, row_no=row_no, raw_data=raw, status='failed',
                    error_code=error_code, error_message=error_message,
                )
                errors.append((row_no, error_code, error_message, raw))
                continue

            with transaction.atomic():
                if not student:
                    student = UserAccount(
                        mobile=mobile or None, student_no=student_no,
                        display_name=name, role_type='student', status='active',
                    )
                    student.set_unusable_password()
                    student.save()
                else:
                    update_fields = []
                    if student.display_name != name:
                        student.display_name = name
                        update_fields.append('display_name')
                    if student_no and student.student_no != student_no:
                        student.student_no = student_no
                        update_fields.append('student_no')
                    if update_fields:
                        student.save(update_fields=update_fields + ['updated_at'])
                relation, created = ClassStudent.objects.get_or_create(
                    class_obj=task.class_obj, student=student,
                    defaults={'join_type': 'import', 'status': 'active'},
                )
                if relation.status != 'active':
                    relation.status = 'active'
                    relation.join_type = 'import'
                    relation.save(update_fields=['status', 'join_type'])
                StudentImportRow.objects.create(
                    task=task, row_no=row_no, student=student, raw_data=raw,
                    status='created' if created else 'matched',
                )
            success += 1

        if errors:
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(['原始行号', '错误码', '错误原因', '姓名', '手机号', '学号'])
            for row_no, code, message, raw in errors:
                writer.writerow([
                    row_no, code, message, raw.get('name', ''),
                    raw.get('mobile', ''), raw.get('student_no', ''),
                ])
            task.error_file_path = default_storage.save(
                f'student-imports/errors_{task.id}.csv',
                ContentFile(('\ufeff' + output.getvalue()).encode('utf-8')),
            )
        task.success_count = success
        task.failed_count = len(errors)
        task.status = 'partially_succeeded' if success and errors else ('succeeded' if success else 'failed')
        task.completed_at = timezone.now()
        task.save(update_fields=[
            'success_count', 'failed_count', 'status',
            'error_file_path', 'completed_at',
        ])
        return {'task_id': str(task.id), 'status': task.status}
    except Exception:
        task.status = 'failed'
        task.completed_at = timezone.now()
        task.save(update_fields=['status', 'completed_at'])
        raise
