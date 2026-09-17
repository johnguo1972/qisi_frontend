"""HTTP endpoints for the isolated classroom wrong-drill workflow."""
from __future__ import annotations

from pathlib import Path
from io import BytesIO
from zipfile import ZipFile, ZIP_DEFLATED

from django.conf import settings
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.permissions import IsTeacherSession
from apps.study.document_import_models import QuestionDocumentImportTask
from apps.study.document_import_views import create_course_document_import

from .classroom_wrong_drill_service import (
    import_number_mapping, queue_wrong_drill_batch, save_mapping_upload, wrong_drill_preflight,
    source_sets_payload, source_set_detail_payload, save_manual_number_mappings,
    remove_source_questions,
)
from .classroom_wrongbook_service import prepare_classroom_matrix
from .models import (
    ClassroomWrongDrillBatch, ClassroomWrongDrillMappingImport,
    ClassroomWrongDrillSourceSet,
)
from .wrongbook_matrix import MatrixError
from .views import make_trace_id


def _error(exc):
    return Response({'code': exc.code, 'message': str(exc), 'data': exc.data, 'trace_id': make_trace_id()}, status=exc.http_status)


def _batch_payload(batch):
    return {
        'batch_id': str(batch.id), 'status': batch.status,
        'requested_count': batch.requested_count, 'generated_count': batch.generated_count,
        'skipped_count': batch.skipped_count, 'failed_count': batch.failed_count,
        'errors': batch.errors or [],
        'packages': [{
            'package_id': str(package.id), 'student_id': str(package.student_id),
            'student_name': package.student.display_name, 'file_name': package.file_name,
            'pdf_file_path': package.pdf_file_path,
            'pdf_download_url': f"{settings.MEDIA_URL.rstrip('/')}/{package.pdf_file_path.lstrip('/')}",
            'mission_id': str(package.mission_id),
            'question_count': package.question_count, 'status': package.status,
            'items': [{
                'wrong_question_no': item.wrong_question_no,
                'drill_question_no': item.drill_question_no,
                'mapping_type': item.mapping_type,
                'stem_preview': str((item.content_snapshot or (item.source_question.question_snapshot if item.source_question else {})).get('stem', ''))[:120],
                'status': item.status,
            } for item in package.items.select_related('source_question').order_by('sort_no')],
        } for package in batch.packages.select_related('student', 'mission').all()],
    }


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated, IsTeacherSession])
def classroom_wrong_drill_sources(request, mission_id):
    try:
        class_id = request.GET.get('class_id') if request.method == 'GET' else (
            request.data.get('class_id') or request.query_params.get('class_id')
        )
        mission, _, _ = prepare_classroom_matrix(mission_id, request.user, class_id)
        if request.method == 'GET':
            return Response({'code': 0, 'message': 'success', 'data': {'sources': source_sets_payload(mission)}, 'trace_id': make_trace_id()})
        document = request.FILES.get('wrongbook_file') or request.FILES.get('file')
        if document is None:
            raise MatrixError('请上传错题练习题 DOCX 文件', 'SOURCE_FILE_REQUIRED', 400)
        if not str(getattr(document, 'name', '')).lower().endswith('.docx'):
            raise MatrixError('错题练习题源仅支持 DOCX 文件', 'SOURCE_FORMAT_INVALID', 400)
        node_id = request.data.get('source_node_id') or None
        node = mission.levels.filter(source_node_id=node_id).first() if node_id else mission.levels.order_by('level_no').first()
        source_set = ClassroomWrongDrillSourceSet.objects.create(
            source_mission=mission, source_node_id=node_id or (node.source_node_id if node else None),
            source_node_name=(node.node_name_snapshot if node else ''), workbook_title=mission.mission_name,
            created_by=request.user, status='pending',
        )
        mapping_file = request.FILES.get('mapping_file')
        if mapping_file is not None:
            mapping_path = save_mapping_upload(mapping_file, source_set_id=source_set.id)
            ClassroomWrongDrillMappingImport.objects.create(
                source_set=source_set, file_path=mapping_path, file_name=mapping_file.name,
                created_by=request.user,
            )
        try:
            response = create_course_document_import(
                request, course=mission.course, tree_node=None,
                import_purpose='wrongbook_drill', source_type='wrongbook_drill',
                wrong_drill_source_set_id=source_set.id,
                storage_prefix='wrong_drill_document_imports',
                upload=document,
            )
        except Exception:
            source_set.status = 'failed'
            source_set.save(update_fields=['status', 'updated_at'])
            raise
        task_id = response.data.get('data', {}).get('task_id') if hasattr(response, 'data') else None
        task = QuestionDocumentImportTask.objects.filter(pk=task_id).first()
        if task:
            source_set.source_file_path = task.source_file
            source_set.save(update_fields=['source_file_path', 'updated_at'])
        return Response({'code': 0, 'message': '错题练习题导入已提交', 'data': {
            'source_set_id': str(source_set.id),
            'task': response.data.get('data') if hasattr(response, 'data') else None,
        }, 'trace_id': make_trace_id()}, status=202)
    except MatrixError as exc:
        return _error(exc)
    except (TypeError, ValueError, OSError) as exc:
        return _error(MatrixError(str(exc) or '错题练习题导入失败', 'SOURCE_IMPORT_INVALID', 400))


@api_view(['GET', 'DELETE'])
@permission_classes([IsAuthenticated, IsTeacherSession])
def classroom_wrong_drill_source_detail(request, mission_id, source_set_id):
    try:
        class_id = request.GET.get('class_id') if request.method == 'GET' else request.data.get('class_id')
        mission, _, _ = prepare_classroom_matrix(mission_id, request.user, class_id)
        source_set = ClassroomWrongDrillSourceSet.objects.filter(pk=source_set_id, source_mission=mission).first()
        if source_set is None:
            raise MatrixError('错题练习题导入源不存在', 'SOURCE_NOT_FOUND', 404)
        if request.method == 'DELETE':
            question_ids = request.data.get('question_ids') or request.query_params.get('question_ids') or []
            if isinstance(question_ids, str):
                question_ids = [item for item in question_ids.split(',') if item]
            removed_count = remove_source_questions(source_set, question_ids)
            return Response({'code': 0, 'message': '已从错题练习册移除', 'data': {'removed_count': removed_count}, 'trace_id': make_trace_id()})
        return Response({'code': 0, 'message': 'success', 'data': source_set_detail_payload(source_set, request.query_params), 'trace_id': make_trace_id()})
    except MatrixError as exc:
        return _error(exc)


@api_view(['POST', 'PATCH'])
@permission_classes([IsAuthenticated, IsTeacherSession])
def classroom_wrong_drill_mapping_import(request, mission_id, source_set_id):
    try:
        mission, _, _ = prepare_classroom_matrix(mission_id, request.user, request.data.get('class_id'))
        source_set = ClassroomWrongDrillSourceSet.objects.filter(pk=source_set_id, source_mission=mission).first()
        if source_set is None:
            raise MatrixError('错题练习题导入源不存在', 'SOURCE_NOT_FOUND', 404)
        if request.method == 'PATCH':
            source_set = save_manual_number_mappings(source_set, request.data.get('mappings'))
            return Response({'code': 0, 'message': '映射关系已保存', 'data': source_set_detail_payload(source_set), 'trace_id': make_trace_id()})
        upload = request.FILES.get('mapping_file') or request.FILES.get('file')
        if upload is None:
            raise MatrixError('请上传映射表 .xlsx 文件', 'MAPPING_REQUIRED', 400)
        path = save_mapping_upload(upload, source_set_id=source_set.id)
        mapping_import = ClassroomWrongDrillMappingImport.objects.create(
            source_set=source_set, file_path=path, file_name=upload.name, created_by=request.user,
        )
        try:
            source_set = import_number_mapping(source_set, mapping_import)
        except Exception as exc:
            mapping_import.status = 'failed'
            mapping_import.errors = [{'reason_code': 'MAPPING_INVALID', 'message': str(exc)[:200]}]
            mapping_import.completed_at = timezone.now()
            mapping_import.save(update_fields=['status', 'errors', 'completed_at'])
            raise MatrixError(str(exc) or '映射表格式错误', 'MAPPING_INVALID', 400)
        parsing = getattr(mapping_import, 'mapping_parse', {'mode': 'header', 'sheets': []})
        message = '映射表导入成功'
        if parsing['mode'] == 'position':
            message = '映射表已按前两列顺序导入'
        return Response({'code': 0, 'message': message, 'data': {
            'sources': source_sets_payload(mission),
            'mapping_parse': parsing,
        }, 'trace_id': make_trace_id()})
    except MatrixError as exc:
        return _error(exc)
    except (TypeError, ValueError, OSError) as exc:
        return _error(MatrixError(str(exc) or '映射表格式错误', 'MAPPING_INVALID', 400))


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsTeacherSession])
def classroom_wrong_drill_generate(request, mission_id):
    try:
        mission, matrix, _ = prepare_classroom_matrix(mission_id, request.user, request.data.get('class_id'))
        batch = queue_wrong_drill_batch(
            mission=mission, matrix=matrix, teacher=request.user,
            source_set_id=request.data.get('source_set_id'), student_ids=request.data.get('student_ids'),
            version=request.data.get('version'),
        )
        return Response({'code': 0, 'message': '精练题生成任务已提交', 'data': _batch_payload(batch), 'trace_id': make_trace_id()}, status=202)
    except MatrixError as exc:
        return _error(exc)
    except (TypeError, ValueError) as exc:
        return _error(MatrixError(str(exc) or '生成参数错误', 'GENERATION_INVALID', 400))


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsTeacherSession])
def classroom_wrong_drill_preflight_view(request, mission_id):
    try:
        mission, matrix, _ = prepare_classroom_matrix(mission_id, request.user, request.GET.get('class_id'))
        data = wrong_drill_preflight(
            mission=mission, matrix=matrix, source_set_id=request.GET.get('source_set_id'),
            student_ids=request.GET.getlist('student_ids'),
        )
        return Response({'code': 0, 'message': 'success', 'data': data, 'trace_id': make_trace_id()})
    except MatrixError as exc:
        return _error(exc)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsTeacherSession])
def classroom_wrong_drill_batch(request, mission_id, batch_id):
    try:
        mission, _, _ = prepare_classroom_matrix(mission_id, request.user, request.GET.get('class_id'))
        batch = ClassroomWrongDrillBatch.objects.filter(pk=batch_id, matrix__source_mission=mission).first()
        if batch is None:
            raise MatrixError('生成批次不存在', 'BATCH_NOT_FOUND', 404)
        return Response({'code': 0, 'message': 'success', 'data': _batch_payload(batch), 'trace_id': make_trace_id()})
    except MatrixError as exc:
        return _error(exc)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsTeacherSession])
def classroom_wrong_drill_bulk_export(request, mission_id, batch_id):
    """Export selected generated student PDFs as one ZIP."""
    try:
        mission, _, _ = prepare_classroom_matrix(mission_id, request.user, request.data.get('class_id'))
        batch = ClassroomWrongDrillBatch.objects.filter(pk=batch_id, matrix__source_mission=mission).first()
        if batch is None:
            raise MatrixError('生成批次不存在', 'BATCH_NOT_FOUND', 404)
        requested = {str(value) for value in (request.data.get('student_ids') or [])}
        packages = batch.packages.filter(status='generated').select_related('student')
        if requested:
            packages = packages.filter(student_id__in=requested)
        packages = list(packages)
        if not packages:
            raise MatrixError('没有可导出的精练题 PDF', 'PDF_NOT_READY', 409)
        output = BytesIO()
        with ZipFile(output, 'w', ZIP_DEFLATED) as archive:
            used = set()
            for package in packages:
                path = Path(settings.MEDIA_ROOT) / package.pdf_file_path
                if not path.exists():
                    continue
                name = package.file_name
                used.add(name)
                archive.write(path, arcname=f'{package.student_id}/{name}')
        if not used:
            raise MatrixError('精练题 PDF 文件不存在', 'PDF_FILE_MISSING', 409)
        relative = Path('exports') / 'wrong_drill' / 'batches' / f'{batch.id}.zip'
        destination = Path(settings.MEDIA_ROOT) / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(output.getvalue())
        return Response({'code': 0, 'message': '批量导出成功', 'data': {
            'file_name': f'{mission.mission_name}-错题精练题.zip',
            'download_url': f"{settings.MEDIA_URL.rstrip('/')}/{relative.as_posix()}",
        }, 'trace_id': make_trace_id()})
    except MatrixError as exc:
        return _error(exc)
