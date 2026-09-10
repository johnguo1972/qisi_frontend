"""Transactional teacher-side student creation and editing services."""

from django.db import transaction

from apps.accounts.models import StudentParentBind, UserAccount
from apps.accounts.roles import grant_user_role, has_user_role

from .models import Class, ClassStudent, ClassTeacher


class StudentManagementError(Exception):
    def __init__(self, code, message, http_status=400):
        self.code = code
        self.message = message
        self.http_status = http_status
        super().__init__(message)


def _teacher_manages_class(user, class_obj):
    return class_obj.creator_teacher_id == user.id or ClassTeacher.objects.filter(
        class_obj=class_obj,
        teacher=user,
    ).exists()


def _get_target_class(user, current_class, target_class_id):
    target_id = target_class_id or current_class.id
    try:
        target = Class.objects.select_for_update().get(
            pk=target_id,
            status='active',
        )
    except Class.DoesNotExist:
        raise StudentManagementError('CLASS_NOT_FOUND', '目标班级不存在', 404)
    if not _teacher_manages_class(user, target):
        raise StudentManagementError('CLASS_FORBIDDEN', '您不是目标班级的管理教师', 403)
    return target


def _validate_target_grade(target, grade_level):
    if target.grade_level and target.grade_level != grade_level:
        raise StudentManagementError(
            'GRADE_CLASS_MISMATCH',
            '所选年级与目标班级年级不一致',
        )


def _check_capacity(target, *, excluding_student_id=None):
    if target.max_students <= 0:
        return
    members = target.class_students.filter(status='active')
    if excluding_student_id:
        members = members.exclude(student_id=excluding_student_id)
    if members.count() >= target.max_students:
        raise StudentManagementError('CLASS_FULL', '目标班级已达到人数上限', 409)


def _lock_account(mobile):
    return UserAccount.objects.select_for_update().filter(mobile=mobile).first()


def _ensure_student(mobile, name, school, current_grade):
    student = _lock_account(mobile)
    if student is None:
        student = UserAccount.objects.create(
            mobile=mobile,
            display_name=name,
            school=school,
            grade_level=current_grade,
            role_type='student',
            status='active',
            password='',
        )
    elif student.status != 'active':
        raise StudentManagementError('ACCOUNT_INACTIVE', '学生账号已停用，不能自动恢复', 409)
    else:
        update_fields = []
        for field, value in (
            ('display_name', name),
            ('school', school),
            ('grade_level', current_grade),
        ):
            if getattr(student, field) != value:
                setattr(student, field, value)
                update_fields.append(field)
        if update_fields:
            student.save(update_fields=update_fields + ['updated_at'])
    grant_user_role(student, 'student', grant_source='teacher_manual')
    return student


def _ensure_parent(student, parent_mobile, parent_name, *, clear_when_empty):
    if not parent_mobile:
        if clear_when_empty:
            StudentParentBind.objects.filter(
                student_user_id=student,
                is_primary=True,
                bind_status='active',
            ).update(is_primary=False, bind_status='removed')
        return None

    parent = _lock_account(parent_mobile)
    if parent is None:
        parent = UserAccount.objects.create(
            mobile=parent_mobile,
            display_name=parent_name,
            role_type='parent',
            status='active',
            password='',
        )
    elif parent.status != 'active':
        raise StudentManagementError('ACCOUNT_INACTIVE', '家长账号已停用，不能自动恢复', 409)
    else:
        if parent_name and parent.display_name != parent_name:
            parent.display_name = parent_name
            parent.save(update_fields=['display_name', 'updated_at'])
    if parent.id == student.id:
        raise StudentManagementError('SELF_PARENT_BINDING', '学生和家长不能使用同一个手机号')
    grant_user_role(parent, 'parent', grant_source='teacher_manual')

    StudentParentBind.objects.select_for_update().filter(
        student_user_id=student,
        is_primary=True,
        bind_status='active',
    ).exclude(parent_user_id=parent).update(is_primary=False)

    relation = StudentParentBind.objects.select_for_update().filter(
        student_user_id=student,
        parent_user_id=parent,
    ).order_by('-bind_status', '-bound_at', '-id').first()
    if relation is None:
        relation = StudentParentBind.objects.create(
            student_user_id=student,
            parent_user_id=parent,
            relation_type='guardian',
            bind_status='active',
            is_primary=True,
        )
    else:
        relation.relation_type = 'guardian'
        relation.bind_status = 'active'
        relation.is_primary = True
        relation.save(update_fields=['relation_type', 'bind_status', 'is_primary'])
    return relation


@transaction.atomic
def add_student(*, user, current_class, data):
    target = _get_target_class(user, current_class, data.get('target_class_id'))
    _validate_target_grade(target, data['grade_level'])
    _check_capacity(target)

    student = _ensure_student(
        data['student_mobile'],
        data['student_name'],
        data['school'],
        data['grade_level'],
    )
    relation = ClassStudent.objects.select_for_update().filter(
        class_obj=target,
        student=student,
    ).first()
    if relation and relation.status == 'active':
        raise StudentManagementError('STUDENT_ALREADY_IN_CLASS', '学生已在目标班级中', 409)
    if relation is None:
        relation = ClassStudent.objects.create(
            class_obj=target,
            student=student,
            grade_level=data['grade_level'],
            class_type=data.get('class_type') or None,
            join_type='manual',
            status='active',
        )
    else:
        relation.grade_level = data['grade_level']
        relation.class_type = data.get('class_type') or None
        relation.join_type = 'manual'
        relation.status = 'active'
        relation.save(update_fields=['grade_level', 'class_type', 'join_type', 'status'])

    _ensure_parent(
        student,
        data.get('parent_mobile', ''),
        data.get('parent_name', ''),
        clear_when_empty=False,
    )
    return ClassStudent.objects.select_related('student', 'class_obj').get(pk=relation.pk)


@transaction.atomic
def update_student(*, user, current_class, student_id, data):
    try:
        relation = ClassStudent.objects.select_for_update().select_related(
            'student', 'class_obj',
        ).get(
            class_obj=current_class,
            student_id=student_id,
            status='active',
        )
    except ClassStudent.DoesNotExist:
        raise StudentManagementError('STUDENT_NOT_IN_CLASS', '学生不在当前班级中', 404)

    student = UserAccount.objects.select_for_update().get(pk=relation.student_id)
    target = _get_target_class(user, current_class, data.get('target_class_id'))
    effective_grade = data.get('grade_level', relation.grade_level or student.grade_level)
    if not effective_grade:
        effective_grade = target.grade_level
    if not effective_grade:
        raise StudentManagementError('GRADE_REQUIRED', '年级不能为空')
    _validate_target_grade(target, effective_grade)

    new_mobile = data.get('student_mobile')
    if new_mobile and new_mobile != student.mobile:
        duplicate = UserAccount.objects.select_for_update().filter(
            mobile=new_mobile,
        ).exclude(pk=student.pk).first()
        if duplicate:
            raise StudentManagementError('MOBILE_EXISTS', '学生手机号已被其他账号使用', 409)
        student.mobile = new_mobile
        update_fields = ['mobile']
    else:
        update_fields = []

    for field in ('student_name', 'school'):
        if field in data:
            model_field = 'display_name' if field == 'student_name' else field
            value = data[field]
            if getattr(student, model_field) != value:
                setattr(student, model_field, value)
                update_fields.append(model_field)
    if student.grade_level != effective_grade:
        student.grade_level = effective_grade
        update_fields.append('grade_level')
    if update_fields:
        student.save(update_fields=update_fields + ['updated_at'])
    if not has_user_role(student, 'student'):
        grant_user_role(student, 'student', grant_source='teacher_manual')

    moving = target.pk != relation.class_obj_id
    if moving:
        _check_capacity(target, excluding_student_id=student.pk)
        existing_target = ClassStudent.objects.select_for_update().filter(
            class_obj=target,
            student=student,
        ).first()
        if existing_target and existing_target.status == 'active':
            raise StudentManagementError('STUDENT_ALREADY_IN_CLASS', '学生已在目标班级中', 409)
        relation.status = 'removed'
        relation.save(update_fields=['status'])
        if existing_target is None:
            relation = ClassStudent.objects.create(
                class_obj=target,
                student=student,
                grade_level=effective_grade,
                class_type=data.get('class_type', relation.class_type) or None,
                join_type='manual',
                status='active',
            )
        else:
            relation = existing_target
            relation.grade_level = effective_grade
            relation.class_type = data.get('class_type', relation.class_type) or None
            relation.join_type = 'manual'
            relation.status = 'active'
            relation.save(update_fields=['grade_level', 'class_type', 'join_type', 'status'])
    else:
        update_fields = []
        if relation.grade_level != effective_grade:
            relation.grade_level = effective_grade
            update_fields.append('grade_level')
        if 'class_type' in data:
            value = data.get('class_type') or None
            if relation.class_type != value:
                relation.class_type = value
                update_fields.append('class_type')
        if update_fields:
            relation.save(update_fields=update_fields)

    if 'parent_mobile' in data or 'parent_name' in data:
        _ensure_parent(
            student,
            data.get('parent_mobile', ''),
            data.get('parent_name', ''),
            clear_when_empty=True,
        )
    return ClassStudent.objects.select_related('student', 'class_obj').get(pk=relation.pk)
