"""Background jobs for institution data imports."""
import csv
import io

from celery import shared_task
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from apps.accounts.models import UserAccount
from apps.accounts.roles import has_user_role
from .models import Class, ClassStudent, ClassTeacher, StudentImportTask, StudentImportRow
from .student_management import StudentManagementError, add_student


def _class_match_key(value):
    return str(value or '').strip().casefold()


def _new_import_format(rows):
    return any(
        key in row
        for row in rows
        for key in ('school', 'class_type', 'parent_name', 'parent_mobile')
    )


def _process_new_student_import(task, rows):
    """Import the current student template and route rows by grade/class."""
    from . import import_views as importer

    teacher_classes = Class.objects.filter(
        Q(class_teachers__teacher=task.uploaded_by) | Q(creator_teacher=task.uploaded_by),
        status='active',
    ).distinct()
    classes_by_key = {}
    for class_obj in teacher_classes:
        key = (_class_match_key(class_obj.grade_level), _class_match_key(class_obj.class_name))
        classes_by_key.setdefault(key, []).append(class_obj)

    seen_mobiles = set()
    errors = []
    success = 0
    for row_no, data in enumerate(rows, start=2):
        raw = dict(data)
        name = str(data.get('name') or '').strip()
        school = str(data.get('school') or '').strip()
        grade_level = str(data.get('grade_level') or '').strip()
        class_name = str(data.get('class_name') or data.get('class_identifier') or '').strip()
        class_type_raw = str(data.get('class_type') or '').strip()
        class_type = importer.normalize_class_type(class_type_raw)
        mobile = str(data.get('mobile') or '').replace(' ', '').strip()
        parent_name = str(data.get('parent_name') or '').strip()
        parent_mobile = str(data.get('parent_mobile') or '').replace(' ', '').strip()
        error_code = ''
        error_message = ''
        target = None

        if not name or len(name) > 64:
            error_code, error_message = 'INVALID_NAME', '学生姓名不能为空且不能超过64个字符'
        elif not school or len(school) > 100:
            error_code, error_message = 'INVALID_SCHOOL', '学校不能为空且不能超过100个字符'
        elif not grade_level:
            error_code, error_message = 'MISSING_GRADE', '年级不能为空，且必须填写教师管理的年级'
        elif not class_name:
            error_code, error_message = 'MISSING_CLASS', '班级不能为空，且必须填写教师管理的班级'
        elif not mobile or not importer.PHONE_RE.fullmatch(mobile):
            error_code, error_message = 'INVALID_MOBILE', '学生手机号不能为空且格式无效'
        elif class_type_raw and not class_type:
            error_code, error_message = 'INVALID_CLASS_TYPE', '班型只能填写S班、A+班或A班'
        elif bool(parent_name) != bool(parent_mobile):
            error_code, error_message = 'PARENT_FIELDS_INCOMPLETE', '家长姓名和家长手机号必须同时填写或同时为空'
        elif parent_mobile and not importer.PHONE_RE.fullmatch(parent_mobile):
            error_code, error_message = 'INVALID_PARENT_MOBILE', '家长手机号格式无效'
        elif parent_mobile and parent_mobile == mobile:
            error_code, error_message = 'SELF_PARENT_BINDING', '学生手机号和家长手机号不能相同'
        elif mobile in seen_mobiles:
            error_code, error_message = 'DUPLICATE_ROW', '文件内学生手机号重复'
        else:
            matched = classes_by_key.get((_class_match_key(grade_level), _class_match_key(class_name)), [])
            if not matched:
                error_code, error_message = 'CLASS_NOT_FOUND', '未匹配到教师管理的年级和班级'
            elif len(matched) > 1:
                error_code, error_message = 'CLASS_AMBIGUOUS', '匹配到多个相同年级和班级，请先处理重复班级'
            else:
                target = matched[0]
                seen_mobiles.add(mobile)

        if error_code:
            StudentImportRow.objects.create(
                task=task, target_class=target, row_no=row_no, raw_data=raw,
                status='failed', error_code=error_code, error_message=error_message,
            )
            errors.append((row_no, error_code, error_message, raw))
            continue

        try:
            add_student(
                user=task.uploaded_by,
                current_class=task.class_obj,
                data={
                    'student_name': name,
                    'school': school,
                    'grade_level': grade_level,
                    'target_class_id': target.id,
                    'class_type': class_type or '',
                    'student_mobile': mobile,
                    'parent_name': parent_name,
                    'parent_mobile': parent_mobile,
                },
            )
        except StudentManagementError as exc:
            StudentImportRow.objects.create(
                task=task, target_class=target, row_no=row_no, raw_data=raw,
                status='failed', error_code=exc.code, error_message=exc.message,
            )
            errors.append((row_no, exc.code, exc.message, raw))
            continue
        except IntegrityError:
            error_code = 'DATA_CONFLICT'
            error_message = '学生或家长手机号、绑定关系存在冲突'
            StudentImportRow.objects.create(
                task=task, target_class=target, row_no=row_no, raw_data=raw,
                status='failed', error_code=error_code, error_message=error_message,
            )
            errors.append((row_no, error_code, error_message, raw))
            continue

        StudentImportRow.objects.create(
            task=task, target_class=target, row_no=row_no, raw_data=raw,
            status='created',
        )
        success += 1

    if errors:
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            '原始行号', '错误码', '错误原因', '学生姓名', '学校', '年级',
            '班级', '班型', '学生手机号', '家长姓名', '家长手机号',
        ])
        for row_no, code, message, raw in errors:
            writer.writerow([
                row_no, code, message, raw.get('name', ''), raw.get('school', ''),
                raw.get('grade_level', ''), raw.get('class_name', ''),
                raw.get('class_type', ''), raw.get('mobile', ''),
                raw.get('parent_name', ''), raw.get('parent_mobile', ''),
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
        if _new_import_format(rows):
            return _process_new_student_import(task, rows)
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
