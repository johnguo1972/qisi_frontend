"""Teacher-side class student import endpoints."""
import csv
import io
import re
import uuid
import zipfile
from xml.etree import ElementTree

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db.models import Q
from django.http import HttpResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.auth import get_request_role
from apps.accounts.models import UserAccount
from apps.accounts.roles import has_user_role
from apps.common.media import media_url
from .models import Class, ClassStudent, ClassTeacher, StudentImportTask


MAX_IMPORT_BYTES = 10 * 1024 * 1024
MAX_IMPORT_ROWS = 5000
PHONE_RE = re.compile(r'^1[3-9]\d{9}$')
HEADER_ALIASES = {
    '姓名': 'name', '学生姓名': 'name', 'name': 'name',
    '学生姓名(必填)': 'name', '学生姓名（必填）': 'name',
    '手机号': 'mobile', '手机号码': 'mobile', '学生手机号': 'mobile',
    'mobile': 'mobile', 'phone': 'mobile',
    '学号': 'student_no', '学生学号': 'student_no', 'student_no': 'student_no',
    '班级标识': 'class_identifier', '班级': 'class_identifier', '班级名称': 'class_name',
    'class': 'class_name', 'class_name': 'class_name',
    '年级': 'grade_level', 'grade': 'grade_level',
    '学校': 'school', '学生学校': 'school',
    '班型': 'class_type', 'class_type': 'class_type',
    '家长姓名': 'parent_name', 'parent_name': 'parent_name',
    '家长手机号': 'parent_mobile', '家长手机': 'parent_mobile', 'parent_mobile': 'parent_mobile',
}

CLASS_TYPE_ALIASES = {
    'S': 'S', 'S班': 'S',
    'A+': 'A_PLUS', 'A+班': 'A_PLUS', 'A_PLUS': 'A_PLUS',
    'A': 'A', 'A班': 'A',
}


def normalize_class_type(value):
    return CLASS_TYPE_ALIASES.get(str(value or '').strip().upper())


def _normalize_header(value):
    header = str(value or '').strip()
    header = re.sub(r'[（(]\s*必填\s*[）)]$', '', header).strip()
    return HEADER_ALIASES.get(header, '')


def _trace():
    return uuid.uuid4().hex[:16]


def _is_teacher_of_class(request, class_id):
    return (
        get_request_role(request) == 'teacher'
        and has_user_role(request.user, 'teacher')
        and ClassTeacher.objects.filter(class_obj_id=class_id, teacher=request.user).exists()
    )


def _read_xlsx(upload):
    """Read the first worksheet without requiring optional openpyxl."""
    with zipfile.ZipFile(upload) as archive:
        ns = {'x': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
        shared = []
        if 'xl/sharedStrings.xml' in archive.namelist():
            root = ElementTree.fromstring(archive.read('xl/sharedStrings.xml'))
            for item in root.findall('x:si', ns):
                shared.append(''.join(node.text or '' for node in item.iter(
                    '{%s}t' % ns['x'])))
        root = ElementTree.fromstring(archive.read('xl/worksheets/sheet1.xml'))
        rows = []

        def column_number(value):
            number = 0
            for char in value:
                number = number * 26 + ord(char.upper()) - 64
            return number

        for row in root.findall('.//x:sheetData/x:row', ns):
            values = {}
            for cell in row.findall('x:c', ns):
                ref = cell.attrib.get('r', '')
                column = ''.join(char for char in ref if char.isalpha())
                value = cell.find('x:v', ns)
                text = value.text if value is not None else ''
                if cell.attrib.get('t') == 's' and text:
                    text = shared[int(text)]
                values[column_number(column)] = text or ''
            if values:
                rows.append([values.get(index, '') for index in range(1, max(values) + 1)])
        return rows


def _read_rows(upload):
    name = str(getattr(upload, 'name', '')).lower()
    if not name.endswith(('.csv', '.xlsx')):
        raise ValueError('仅支持 CSV 或 XLSX 文件')
    if upload.size > MAX_IMPORT_BYTES:
        raise ValueError('文件不能超过 10MB')
    if name.endswith('.xlsx'):
        upload.seek(0)
        rows = _read_xlsx(upload)
    else:
        raw = upload.read()
        try:
            content = raw.decode('utf-8-sig')
        except UnicodeDecodeError:
            content = raw.decode('gb18030')
        rows = list(csv.reader(io.StringIO(content)))
    if not rows:
        raise ValueError('文件没有数据')
    rows = [row for row in rows if not (
        row and str(row[0]).strip().startswith('#')
    )]
    if not rows:
        raise ValueError('文件没有表头')
    headers = [_normalize_header(value) for value in rows[0]]
    new_format = 'school' in headers or 'class_type' in headers or 'parent_mobile' in headers
    if new_format:
        required_headers = {
            'name', 'school', 'grade_level', 'class_name',
            'class_type', 'mobile', 'parent_name', 'parent_mobile',
        }
        # The alias for the new template's 班级 column is normalized below.
        if 'class_identifier' in headers:
            headers[headers.index('class_identifier')] = 'class_name'
        missing = required_headers.difference(headers)
        if missing:
            raise ValueError('导入模板缺少列：' + '、'.join(sorted(missing)))
    else:
        if 'mobile' not in headers and 'student_no' not in headers:
            raise ValueError('手机号和学号至少提供一个')
        if 'name' not in headers:
            raise ValueError('缺少姓名列')
    result = []
    for values in rows[1:]:
        data = {
            header: str(values[index]).strip() if index < len(values) else ''
            for index, header in enumerate(headers) if header
        }
        if any(data.values()):
            result.append(data)
    if len(result) > MAX_IMPORT_ROWS:
        raise ValueError(f'最多导入 {MAX_IMPORT_ROWS} 行')
    return result


def _task_data(task):
    return {
        'id': str(task.id), 'class_id': str(task.class_obj_id),
        'status': task.status, 'total_count': task.total_count,
        'success_count': task.success_count, 'failed_count': task.failed_count,
        'error_file_path': task.error_file_path or None,
        'error_download_url': media_url(task.error_file_path) if task.error_file_path else None,
        'created_at': task.created_at, 'completed_at': task.completed_at,
    }


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def import_template(request, class_id):
    if not _is_teacher_of_class(request, class_id):
        return Response({'code': 403, 'message': '无权访问该班级', 'data': None, 'trace_id': _trace()}, status=403)
    classes = Class.objects.filter(
        Q(class_teachers__teacher=request.user) | Q(creator_teacher=request.user),
        status='active',
    ).distinct().order_by('grade_level', 'class_name')
    class_options = '；'.join(
        f'{item.grade_level or "未设置年级"}/{item.class_name}'
        for item in classes
    )
    content = (
        '\ufeff# 年级和班级请填写教师管理范围内的值；班型填写 S班、A+班或A班\n'
        f'# 可选年级/班级：{class_options or "暂无可选班级"}\n'
        '学生姓名(必填),学校(必填),年级(必填),班级(必填),班型(必填),学生手机号(必填),家长姓名,家长手机号\n'
    )
    response = HttpResponse(
        content,
        content_type='text/csv; charset=utf-8',
    )
    response['Content-Disposition'] = 'attachment; filename="student-import-template.csv"'
    return response


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def import_students(request, class_id):
    if not _is_teacher_of_class(request, class_id):
        return Response({'code': 403, 'message': '无权操作该班级', 'data': None, 'trace_id': _trace()}, status=403)
    try:
        cls = Class.objects.select_related('institution').get(pk=class_id, status='active')
    except Class.DoesNotExist:
        return Response({'code': 404, 'message': '班级不存在', 'data': None, 'trace_id': _trace()}, status=404)
    upload = request.FILES.get('file') or request.FILES.get('students')
    if not upload:
        return Response({'code': 400, 'message': '请上传文件', 'data': None, 'trace_id': _trace()}, status=400)
    try:
        rows = _read_rows(upload)
    except (ValueError, zipfile.BadZipFile, ElementTree.ParseError, UnicodeError, IndexError) as exc:
        return Response({'code': 400, 'message': str(exc), 'data': None, 'trace_id': _trace()}, status=400)
    upload.seek(0)
    storage_path = default_storage.save(
        f'student-imports/{uuid.uuid4().hex}_{upload.name}', ContentFile(upload.read())
    )
    task = StudentImportTask.objects.create(
        institution=cls.institution, class_obj=cls, uploaded_by=request.user,
        file_path=storage_path, status='validating', total_count=len(rows),
    )
    from .tasks import process_student_import

    process_student_import.delay(str(task.id), rows)
    task.refresh_from_db()
    return Response({
        'code': 0,
        'message': '导入任务已提交',
        'data': _task_data(task),
        'trace_id': _trace(),
    }, status=202 if task.status == 'validating' else 200)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def import_status(request, task_id):
    try:
        task = StudentImportTask.objects.get(pk=task_id, uploaded_by=request.user)
    except StudentImportTask.DoesNotExist:
        return Response({'code': 404, 'message': '导入任务不存在', 'data': None, 'trace_id': _trace()}, status=404)
    return Response({'code': 0, 'data': _task_data(task), 'trace_id': _trace()})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def import_errors(request, task_id):
    try:
        task = StudentImportTask.objects.get(pk=task_id, uploaded_by=request.user)
    except StudentImportTask.DoesNotExist:
        return Response({'code': 404, 'message': '导入任务不存在', 'data': None, 'trace_id': _trace()}, status=404)
    rows = task.rows.filter(status='failed').order_by('row_no')
    return Response({'code': 0, 'data': {
        'task_id': str(task.id),
        'download_url': media_url(task.error_file_path) if task.error_file_path else None,
        'items': [
            {
                'row_no': row.row_no, 'error_code': row.error_code,
                'error_message': row.error_message, 'raw_data': row.raw_data,
            }
            for row in rows
        ],
    }, 'trace_id': _trace()})
