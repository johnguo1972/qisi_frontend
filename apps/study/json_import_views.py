"""JSON数据包导入：上传ZIP → 解压 → 解析JSON → 导入题目和图片"""
import os
import json
import uuid
import zipfile
import shutil
import logging
from pathlib import Path
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.parser.models import ExamQuestion, QuestionOption, QuestionImage
from apps.papers.models import ExamPaper, ParseTask
from apps.common.codegen import generate_question_system_id
from apps.common.media import media_url
from apps.study.formula_assets import (
    FormulaAssetConversionError,
    convert_formula_asset,
    formula_key_from_asset,
    render_formula_placeholders,
)

logger = logging.getLogger(__name__)


def make_trace_id() -> str:
    return uuid.uuid4().hex[:16]


# 题型映射：JSON格式 → 数据库格式
QUESTION_TYPE_MAP = {
    'single_choice': 'single_choice',
    'multiple_choice': 'multiple_choice',
    'fill_blank': 'fill_blank',
    'short_answer': 'short_answer',
    'essay': 'essay',
    'true_false': 'true_false',
    'computation': 'computation',
    'proof': 'proof',
    'solution': 'short_answer',  # 解答题映射为简答题
    # 真实数据包中出现的题型（深圳中学八年级物理期中试题）
    'calculation': 'computation',           # 计算题→计算题
    'experiment': 'short_answer',           # 实验探究题→简答题
    'reading_comprehension': 'short_answer', # 阅读理解题→简答题
    'unknown': 'unknown',
}

# 学科映射：中文/英文 → 英文代码（与 KnowledgePoint.SUBJECT_CHOICES 一致）
SUBJECT_MAP = {
    '数学': 'math', 'math': 'math',
    '物理': 'physics', 'physics': 'physics',
    '化学': 'chemistry', 'chemistry': 'chemistry',
    '语文': 'chinese', 'chinese': 'chinese',
    '英语': 'english', 'english': 'english',
}

# 字母代码映射（用于 generate_question_system_id）
SUBJECT_LETTER_MAP = {
    'math': 'M', '数学': 'M',
    'physics': 'P', '物理': 'P',
    'chemistry': 'C', '化学': 'C',
    'chinese': 'Z', '语文': 'Z',
    'english': 'E', '英语': 'E',
}


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def import_json_package(request):
    """
    上传ZIP压缩包，解析JSON和图片，批量导入题目。

    请求: multipart/form-data, field: file (zip文件)
    响应: { code, message, data: { paper_id, imported, errors, error_details } }
    """
    uploaded_file = request.FILES.get('file')
    if not uploaded_file:
        return Response(
            {'code': 400, 'message': '请上传ZIP文件', 'data': None, 'trace_id': make_trace_id()},
            status=400
        )

    if not uploaded_file.name.lower().endswith('.zip'):
        return Response(
            {'code': 400, 'message': '仅支持 .zip 格式文件', 'data': None, 'trace_id': make_trace_id()},
            status=400
        )

    # 限制文件大小 (50MB)
    if uploaded_file.size > 50 * 1024 * 1024:
        return Response(
            {'code': 400, 'message': '文件大小不能超过50MB', 'data': None, 'trace_id': make_trace_id()},
            status=400
        )

    # 保存ZIP到临时目录
    temp_dir = settings.MEDIA_ROOT / 'temp_imports' / str(uuid.uuid4())
    temp_dir.mkdir(parents=True, exist_ok=True)
    zip_path = temp_dir / uploaded_file.name

    with open(zip_path, 'wb') as f:
        for chunk in uploaded_file.chunks():
            f.write(chunk)

    try:
        # 先解压读取paper信息，创建ExamPaper后再创建ParseTask
        with zipfile.ZipFile(zip_path, 'r') as zf:
            for name in zf.namelist():
                if name.startswith('/') or '..' in name:
                    raise ValueError(f'不安全的文件路径: {name}')
            zf.extractall(temp_dir)

        # 读取题目数据获取paper信息
        paper_info = _read_paper_info(temp_dir)
        subject_name = paper_info.get('subject', '物理')

        # 创建 ExamPaper（paper_code 由 signal 自动生成）
        paper = ExamPaper.objects.create(
            title=paper_info.get('title', 'JSON导入试卷'),
            subject=subject_name,
            grade=paper_info.get('grade', ''),
            stage='junior' if '年级' in str(paper_info.get('grade', '')) else 'senior',
            paper_type='json_import',
            region=paper_info.get('source_file', ''),
            source_file_path=str(zip_path.relative_to(settings.MEDIA_ROOT)),
            status='reviewing',
            uploaded_by=request.user,
        )

        # 创建解析任务记录（必须有paper）
        task = ParseTask.objects.create(
            paper=paper,
            task_type='json_import',
            status='running',
            progress=0,
            current_step='正在导入题目',
        )

        result = _process_json_import(temp_dir, task, paper, request.user)
        task.status = 'success'
        task.progress = 100
        task.current_step = '导入完成'
        task.save()

        return Response({
            'code': 0,
            'message': f'导入成功，共导入 {result["imported"]} 题',
            'data': result,
            'trace_id': make_trace_id(),
        })
    except Exception as e:
        logger.exception(f'JSON import failed: {e}')
        task.status = 'failed'
        task.error_message = str(e)
        task.save()
        return Response(
            {'code': 500, 'message': f'导入失败: {str(e)}', 'data': None, 'trace_id': make_trace_id()},
            status=500
        )
    finally:
        # 清理临时文件
        shutil.rmtree(temp_dir, ignore_errors=True)


def _read_paper_info(temp_dir):
    """从解压目录中读取试卷信息（不创建数据库记录）。"""
    temp_dir = Path(temp_dir)

    # 查找 all_questions.json（可能在根目录或子目录中）
    all_q_path = temp_dir / 'all_questions.json'
    if not all_q_path.exists():
        # 搜索子目录
        matches = list(temp_dir.glob('**/all_questions.json'))
        if matches:
            all_q_path = matches[0]

    if all_q_path.exists():
        with open(all_q_path, 'r', encoding='utf-8') as f:
            package = json.load(f)
        return package.get('paper', {})

    # 查找 manifest.json
    manifest_path = temp_dir / 'manifest.json'
    if not manifest_path.exists():
        matches = list(temp_dir.glob('**/manifest.json'))
        if matches:
            manifest_path = matches[0]

    if manifest_path.exists():
        with open(manifest_path, 'r', encoding='utf-8') as f:
            manifest = json.load(f)
        combined_file = manifest.get('combined_json')
        if combined_file:
            combined_path = manifest_path.parent / combined_file
            if combined_path.exists():
                with open(combined_path, 'r', encoding='utf-8') as f:
                    pkg = json.load(f)
                return pkg.get('paper', manifest)
        return manifest

    return {}


def _process_json_import(temp_dir, task, paper, user):
    """处理JSON导入的核心逻辑（paper已创建）。"""
    temp_dir = Path(temp_dir)
    task.progress = 5
    task.current_step = '正在查找题目数据'
    task.save()

    # 查找并加载题目数据
    questions_data = []

    # 查找 all_questions.json（可能在根目录或子目录中）
    all_q_path = temp_dir / 'all_questions.json'
    if not all_q_path.exists():
        matches = list(temp_dir.glob('**/all_questions.json'))
        if matches:
            all_q_path = matches[0]

    if all_q_path.exists():
        with open(all_q_path, 'r', encoding='utf-8') as f:
            package = json.load(f)
        paper_info = package.get('paper', {})
        raw_questions = package.get('questions', [])
        # 如果是 paper_with_questions 格式
        if isinstance(raw_questions, list):
            questions_data = raw_questions
        else:
            questions_data = [raw_questions] if raw_questions else []

    # 方案2: manifest.json + combined_json
    if not questions_data:
        manifest_path = temp_dir / 'manifest.json'
        if not manifest_path.exists():
            matches = list(temp_dir.glob('**/manifest.json'))
            if matches:
                manifest_path = matches[0]

        if manifest_path.exists():
            with open(manifest_path, 'r', encoding='utf-8') as f:
                manifest = json.load(f)
            paper_info = manifest.get('paper', manifest)

            combined_file = manifest.get('combined_json')
            if combined_file:
                combined_path = manifest_path.parent / combined_file
                if combined_path.exists():
                    with open(combined_path, 'r', encoding='utf-8') as f:
                        pkg = json.load(f)
                    questions_data = pkg.get('questions', [])

            # 方案3: manifest.json + files 列表
            if not questions_data:
                for qfile in manifest.get('files', []):
                    qpath = manifest_path.parent / qfile
                    if qpath.exists():
                        with open(qpath, 'r', encoding='utf-8') as f:
                            questions_data.append(json.load(f))

    # 方案4: 直接扫描 questions/ 目录
    if not questions_data:
        q_dir = temp_dir / 'questions'
        if not q_dir.exists():
            matches = list(temp_dir.glob('**/questions'))
            if matches:
                q_dir = matches[0]
        if q_dir.exists():
            for qfile in sorted(q_dir.glob('*.json')):
                with open(qfile, 'r', encoding='utf-8') as f:
                    questions_data.append(json.load(f))

    if not questions_data:
        raise ValueError('未在ZIP中找到有效的题目数据（需要 all_questions.json 或 manifest.json）')

    task.progress = 10
    task.current_step = f'找到 {len(questions_data)} 道题目，开始导入'
    task.save()

    # 更新试卷题目总数
    paper.total_questions = len(questions_data)
    paper.save(update_fields=['total_questions'])

    # 逐题导入
    imported_count = 0
    error_count = 0
    errors = []
    total = len(questions_data)

    # 找到 assets 目录（可能在根目录或子目录中）
    assets_dir = temp_dir / 'assets'
    if not assets_dir.exists():
        matches = list(temp_dir.glob('**/assets'))
        if matches:
            assets_dir = matches[0]

    for i, qdata in enumerate(questions_data):
        try:
            _import_single_question(qdata, paper, assets_dir, temp_dir)
            imported_count += 1
        except Exception as e:
            error_count += 1
            qno = qdata.get('question_no', f'未知(索引{i})')
            errors.append({'question_no': qno, 'error': str(e)[:200]})
            logger.warning(f'Failed to import question {qno}: {e}')

        # 更新进度 (10% ~ 95%)
        task.progress = 10 + int(85 * (i + 1) / total)
        task.current_step = f'正在导入第 {i + 1}/{total} 题'
        task.save()

    # 5. 更新试卷
    paper.total_questions = imported_count
    paper.save(update_fields=['total_questions'])

    return {
        'paper_id': str(paper.id),
        'paper_title': paper.title,
        'imported': imported_count,
        'errors': error_count,
        'error_details': errors[:20],
    }


@transaction.atomic
def _import_single_question(qdata, paper, assets_dir, base_dir):
    """导入单道题目及其关联图片。"""
    qtype_raw = qdata.get('question_type', 'unknown')
    qtype = QUESTION_TYPE_MAP.get(qtype_raw, 'unknown')

    # 使用字母代码生成 system_id（与现有 QuestionIDCounter 保持一致）
    system_id = generate_question_system_id(SUBJECT_LETTER_MAP.get(paper.subject, 'P'))

    # 提取答案
    answer_raw = qdata.get('answer', '')
    if isinstance(answer_raw, dict):
        answer_raw = answer_raw.get('raw', '')

    # 提取页码
    source = qdata.get('source', {})
    page_start = source.get('page_start', 0) if isinstance(source, dict) else 0
    page_end = source.get('page_end', page_start) if isinstance(source, dict) else page_start

    # 质量标记
    quality = qdata.get('quality', {})
    needs_review = quality.get('requires_review', True) if isinstance(quality, dict) else True

    question = ExamQuestion.objects.create(
        paper=paper,
        system_id=system_id,
        question_no=str(qdata.get('question_no', '')),
        paper_question_no=f"JSON-{paper.paper_code or 'JSON'}-{qdata.get('question_no', '')}",
        question_type=qtype,
        subject=SUBJECT_MAP.get(paper.subject, 'P'),  # 设置为字母代码，与前端查询一致
        section_title=qdata.get('section', ''),
        stem=qdata.get('stem', ''),
        answer=str(answer_raw) if answer_raw else '',
        analysis=qdata.get('analysis', ''),
        solution='',
        knowledge_points=[],  # JSON包中通常没有知识点ID，留空待后续标注
        difficulty=3.0,       # 默认中等难度
        page_start=page_start,
        page_end=page_end,
        confidence=1.0,
        need_review=needs_review,
        review_status='need_review',
        parse_status='json_imported',
        source_collection=paper.title,  # 使用试卷标题作为来源题集
        creator_name=paper.uploaded_by.display_name if paper.uploaded_by else '',
        collected_at=timezone.now(),
        barcode_data=system_id,  # 使用system_id作为条形码数据
    )

    # 创建选项
    created_options = []
    options = qdata.get('options', [])
    if options and qtype in ('single_choice', 'multiple_choice'):
        for i, opt in enumerate(options):
            created_options.append(QuestionOption.objects.create(
                question=question,
                option_label=opt.get('label', chr(65 + i)),
                content=opt.get('content', ''),
                sort_order=i,
            ))

    # 导入插图
    for index, ill in enumerate(qdata.get('illustrations', [])):
        _import_asset_image(
            ill, question, paper, assets_dir, image_type='diagram', sort_order=index
        )

    # 导入公式图片
    formula_urls = {}
    for index, fa in enumerate(qdata.get('formula_assets', [])):
        image = _import_asset_image(
            fa, question, paper, assets_dir, image_type='formula', sort_order=index
        )
        if image:
            formula_urls[formula_key_from_asset(fa)] = media_url(image.file_path)

    missing_formula_keys = []
    question.stem_html, missing = render_formula_placeholders(question.stem, formula_urls)
    missing_formula_keys.extend(missing)
    question.answer, missing = render_formula_placeholders(question.answer, formula_urls)
    missing_formula_keys.extend(missing)
    question.analysis, missing = render_formula_placeholders(question.analysis, formula_urls)
    missing_formula_keys.extend(missing)

    for option in created_options:
        option.content_html, missing = render_formula_placeholders(option.content, formula_urls)
        missing_formula_keys.extend(missing)
        option.save(update_fields=['content_html', 'updated_at'])

    question.formula_need_review = bool(missing_formula_keys)
    question.save(update_fields=[
        'stem_html', 'answer', 'analysis', 'formula_need_review', 'updated_at'
    ])

    return question


def _import_asset_image(
    asset_data, question, paper, assets_dir, image_type='other', sort_order=0
):
    """导入单个资源图片（插图或公式图片）。"""
    file_rel = asset_data.get('file', '')
    if not file_rel:
        return None

    # 解析图片实际路径
    # JSON中路径如 "../assets/q01_stem.png" 或 "../assets/formula_02.png"
    asset_filename = os.path.basename(file_rel)
    src_path = assets_dir / asset_filename

    if not src_path.exists():
        if image_type == 'formula':
            raise FormulaAssetConversionError(f'Formula image not found: {file_rel}')
        logger.warning(f'Image not found: {file_rel} (looked in {assets_dir})')
        return None

    # 复制到 media 目录
    dest_dir = settings.MEDIA_ROOT / 'exams' / 'json_imports' / str(paper.id)
    dest_dir.mkdir(parents=True, exist_ok=True)

    original_dest_name = f'{question.id}_{asset_filename}'
    original_dest_path = dest_dir / original_dest_name
    shutil.copy2(str(src_path), str(original_dest_path))

    display_path = original_dest_path
    if image_type == 'formula':
        display_path = convert_formula_asset(original_dest_path, original_dest_path)

    rel_media = f'exams/json_imports/{paper.id}/{display_path.name}'
    rel_original = f'exams/json_imports/{paper.id}/{original_dest_name}'
    description = asset_data.get('alt_text') or asset_data.get('recognized_text')
    if image_type == 'formula' and not description:
        description = formula_key_from_asset(asset_data)

    return QuestionImage.objects.create(
        paper=paper,
        question=question,
        image_type=image_type,
        file_path=rel_media,
        original_file_path=rel_original,
        description=description or '',
        sort_order=sort_order,
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def import_json_task_status(request, task_id):
    """获取JSON导入任务进度。"""
    try:
        task = ParseTask.objects.get(pk=task_id, task_type='json_import')
        return Response({
            'code': 0,
            'data': {
                'status': task.status,
                'progress': task.progress,
                'current_step': task.current_step,
                'error_message': task.error_message,
            }
        })
    except ParseTask.DoesNotExist:
        return Response(
            {'code': 404, 'message': '任务不存在', 'data': None, 'trace_id': make_trace_id()},
            status=404
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def json_import_history(request):
    """获取JSON导入历史（当前用户）。"""
    qs = ParseTask.objects.filter(
        task_type='json_import',
        paper__uploaded_by=request.user,
    ).order_by('-created_at')[:50]

    items = []
    for task in qs:
        items.append({
            'id': str(task.id),
            'title': task.paper.title if task.paper else '未知试卷',
            'status': task.status,
            'progress': task.progress,
            'question_count': task.paper.total_questions if task.paper else 0,
            'created_at': task.created_at.isoformat() if task.created_at else '',
            'error_message': task.error_message or '',
        })

    return Response({
        'code': 0, 'message': 'success',
        'data': items,
        'trace_id': make_trace_id(),
    })
