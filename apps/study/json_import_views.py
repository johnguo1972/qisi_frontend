"""JSON数据包导入：上传ZIP → 解压 → 解析JSON → 导入题目和图片"""
import os
import json
import uuid
import zipfile
import shutil
import logging
import hashlib
import re
import time
from pathlib import Path
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.parser.models import (
    ExamQuestion,
    QuestionContentFingerprint,
    QuestionImage,
    QuestionOption,
)
from apps.parser.question_identity import (
    activate_content_fingerprint,
    build_content_fingerprint,
    reserve_content_fingerprint,
)
from apps.papers.models import ExamPaper, ParseTask
from apps.common.codegen import generate_question_system_id
from apps.common.media import media_url
from apps.common.question_types import CANONICAL_QUESTION_TYPES, normalize_question_type
from apps.study.formula_assets import (
    FormulaAssetConversionError,
    convert_formula_asset,
    formula_key_from_asset,
    render_formula_placeholders,
)
from apps.study.ingestion import finish_ingestion_batch, start_ingestion_batch

logger = logging.getLogger(__name__)

FORMULA_PLACEHOLDER_RE = re.compile(r'\[\[formula:([^\]]+)\]\]')
FINGERPRINT_RECHECK_ATTEMPTS = 3
FINGERPRINT_RECHECK_DELAY_SECONDS = 0.01


class FingerprintReservationPendingError(RuntimeError):
    """Raised when another import has not yet activated a fingerprint."""


class SourceAssetNotFoundError(ValueError):
    """Raised when a declared JSON image asset cannot be resolved."""


def make_trace_id() -> str:
    return uuid.uuid4().hex[:16]


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

    batch = start_ingestion_batch(
        actor=request.user,
        source_type='json_import',
        source_name=uploaded_file.name,
    )

    if not uploaded_file.name.lower().endswith('.zip'):
        finish_ingestion_batch(
            batch,
            total_read=0,
            created_count=0,
            skipped_existing_count=0,
            skipped_in_package_count=0,
            failed_count=1,
        )
        return Response(
            {'code': 400, 'message': '仅支持 .zip 格式文件', 'data': None, 'trace_id': make_trace_id()},
            status=400
        )

    # 限制文件大小 (50MB)
    if uploaded_file.size > 50 * 1024 * 1024:
        finish_ingestion_batch(
            batch,
            total_read=0,
            created_count=0,
            skipped_existing_count=0,
            skipped_in_package_count=0,
            failed_count=1,
        )
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
        with zipfile.ZipFile(zip_path, 'r') as zf:
            for name in zf.namelist():
                if name.startswith('/') or '..' in name:
                    raise ValueError(f'不安全的文件路径: {name}')
            zf.extractall(temp_dir)

        result = _process_json_import(
            temp_dir=temp_dir,
            user=request.user,
            batch=batch,
            source_file_path=str(zip_path.relative_to(settings.MEDIA_ROOT)),
        )

        return Response({
            'code': 0,
            'message': f'导入成功，共导入 {result["imported"]} 题',
            'data': result,
            'trace_id': make_trace_id(),
        })
    except Exception as e:
        logger.exception(f'JSON import failed: {e}')
        if batch and batch.status == batch.Status.RUNNING:
            finish_ingestion_batch(
                batch,
                total_read=0,
                created_count=0,
                skipped_existing_count=0,
                skipped_in_package_count=0,
                failed_count=1,
            )
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


def _process_json_import(*, temp_dir, user, batch, source_file_path):
    """Preflight a package, then lazily create import records for new content only."""
    paper_info, questions_data, assets_dir = _load_json_package(temp_dir)
    counters = {
        'total_read': len(questions_data),
        'imported': 0,
        'skipped_existing': 0,
        'skipped_in_package': 0,
        'failed': 0,
    }
    errors = []
    duplicate_details = []
    prepared = []
    fingerprints_in_package = set()

    for index, raw_question in enumerate(questions_data):
        try:
            qdata, fingerprint = _preflight_question(raw_question, assets_dir)
        except Exception as exc:
            counters['failed'] += 1
            errors.append(_question_error(raw_question, index, exc))
            continue
        if fingerprint in fingerprints_in_package:
            counters['skipped_in_package'] += 1
            _append_duplicate_detail(
                duplicate_details,
                source_index=index,
                category='in_package',
                fingerprint=fingerprint,
            )
            continue
        fingerprints_in_package.add(fingerprint)
        try:
            registry = _active_fingerprint_or_raise(fingerprint)
        except FingerprintReservationPendingError as exc:
            counters['failed'] += 1
            errors.append(_question_error(raw_question, index, exc))
            continue
        if registry:
            counters['skipped_existing'] += 1
            _append_duplicate_detail(
                duplicate_details,
                source_index=index,
                category='existing',
                fingerprint=fingerprint,
                registry=registry,
            )
            continue
        prepared.append((qdata, fingerprint, index))

    paper = None
    task = None
    for qdata, fingerprint, index in prepared:
        created_paper = False
        created_media_paths = []
        try:
            with transaction.atomic():
                registry, reserved = reserve_content_fingerprint(fingerprint)
                if not reserved:
                    registry = _active_fingerprint_or_raise(fingerprint)
                    if registry:
                        counters['skipped_existing'] += 1
                        _append_duplicate_detail(
                            duplicate_details,
                            source_index=index,
                            category='existing',
                            fingerprint=fingerprint,
                            registry=registry,
                        )
                        continue
                    raise FingerprintReservationPendingError(
                        'Fingerprint reservation did not resolve to an active question'
                    )
                if paper is None:
                    paper = _create_json_import_paper(paper_info, user, source_file_path)
                    task = ParseTask.objects.create(
                        paper=paper,
                        task_type='json_import',
                        status='running',
                        progress=0,
                        current_step='正在导入题目',
                    )
                    batch.paper = paper
                    batch.save(update_fields=['paper'])
                    created_paper = True
                question = _import_single_question(
                    qdata,
                    paper,
                    assets_dir,
                    temp_dir,
                    created_media_paths=created_media_paths,
                )
                activate_content_fingerprint(registry, question)
                counters['imported'] += 1
        except Exception as exc:
            _cleanup_media_paths(created_media_paths)
            if created_paper:
                paper = None
                task = None
            counters['failed'] += 1
            errors.append(_question_error(qdata, index, exc))
            logger.warning('Failed to import JSON question %s: %s', qdata.get('question_no'), exc)

    if paper:
        paper.total_questions = counters['imported']
        paper.save(update_fields=['total_questions'])
        task.status = 'success'
        task.progress = 100
        task.current_step = '导入完成'
        task.save(update_fields=['status', 'progress', 'current_step'])

    _complete_duplicate_details(duplicate_details)

    finish_ingestion_batch(
        batch,
        total_read=counters['total_read'],
        created_count=counters['imported'],
        skipped_existing_count=counters['skipped_existing'],
        skipped_in_package_count=counters['skipped_in_package'],
        failed_count=counters['failed'],
    )
    return {
        'paper_id': str(paper.id) if paper else None,
        'paper_title': paper.title if paper else None,
        'ingestion_batch_id': str(batch.id),
        **counters,
        'errors': counters['failed'],
        'error_details': errors[:20],
        'details': duplicate_details,
    }


def _load_json_package(temp_dir):
    """Load supported package layouts without writing papers, tasks, or media."""
    temp_dir = Path(temp_dir)
    paper_info = _read_paper_info(temp_dir)
    questions_data = []
    all_q_path = _find_package_file(temp_dir, 'all_questions.json')
    if all_q_path:
        with open(all_q_path, 'r', encoding='utf-8') as package_file:
            package = json.load(package_file)
        raw_questions = package.get('questions', [])
        questions_data = raw_questions if isinstance(raw_questions, list) else [raw_questions] if raw_questions else []
    if not questions_data:
        manifest_path = _find_package_file(temp_dir, 'manifest.json')
        if manifest_path:
            with open(manifest_path, 'r', encoding='utf-8') as manifest_file:
                manifest = json.load(manifest_file)
            combined_file = manifest.get('combined_json')
            if combined_file and (combined_path := manifest_path.parent / combined_file).exists():
                with open(combined_path, 'r', encoding='utf-8') as combined:
                    questions_data = json.load(combined).get('questions', [])
            if not questions_data:
                for qfile in manifest.get('files', []):
                    qpath = manifest_path.parent / qfile
                    if qpath.exists():
                        with open(qpath, 'r', encoding='utf-8') as question_file:
                            questions_data.append(json.load(question_file))
    if not questions_data:
        questions_dir = _find_package_file(temp_dir, 'questions')
        if questions_dir and questions_dir.is_dir():
            for qfile in sorted(questions_dir.glob('*.json')):
                with open(qfile, 'r', encoding='utf-8') as question_file:
                    questions_data.append(json.load(question_file))
    if not questions_data:
        raise ValueError('未在ZIP中找到有效的题目数据（需要 all_questions.json 或 manifest.json）')
    assets_dir = _find_package_file(temp_dir, 'assets') or temp_dir / 'assets'
    return paper_info, questions_data, assets_dir


def _find_package_file(temp_dir, name):
    direct = Path(temp_dir) / name
    if direct.exists():
        return direct
    matches = list(Path(temp_dir).glob(f'**/{name}'))
    return matches[0] if matches else None


def _preflight_question(raw_question, assets_dir):
    """Resolve assets and build a stable content-v1 fingerprint before importing."""
    qdata = dict(raw_question)
    source_type = str(qdata.get('question_type', '') or '')
    answer = _answer_raw(qdata.get('answer', ''))
    canonical_type = normalize_question_type(
        source_type,
        stem=qdata.get('stem', ''),
        options=qdata.get('options') or [],
        answer=answer,
    )
    if canonical_type not in CANONICAL_QUESTION_TYPES:
        raise ValueError('unsupported_question_type')
    qdata['question_type'] = canonical_type
    if source_type and source_type != canonical_type:
        qdata['source_question_type'] = source_type
    else:
        qdata.pop('source_question_type', None)
    formula_identities = {}
    image_hashes = []
    for asset in qdata.get('illustrations', []):
        image_hashes.append(_hash_source_asset(asset, assets_dir, required=True))
    for asset in qdata.get('formula_assets', []):
        asset_hash = _hash_source_asset(asset, assets_dir, required=True)
        image_hashes.append(asset_hash)
        identity = str(asset.get('recognized_text') or asset.get('alt_text') or asset_hash)
        formula_identities[formula_key_from_asset(asset)] = identity

    def normalize_formulas(value):
        return FORMULA_PLACEHOLDER_RE.sub(
            lambda match: f'[[formula:{formula_identities.get(match.group(1), match.group(1))}]]',
            str(value or ''),
        )

    options = qdata.get('options') or []
    fingerprint = build_content_fingerprint(
        stem=normalize_formulas(qdata.get('stem', '')),
        options=[normalize_formulas(option.get('content', '')) for option in options],
        formula_texts=list(formula_identities.values()),
        image_hashes=image_hashes,
    )
    return qdata, fingerprint


def _hash_source_asset(asset_data, assets_dir, *, required):
    file_rel = asset_data.get('file', '')
    if not file_rel:
        if required:
            raise SourceAssetNotFoundError('Image asset path is required')
        return ''
    source_path = Path(assets_dir) / os.path.basename(file_rel)
    if not source_path.exists():
        if required:
            raise SourceAssetNotFoundError(f'Image asset not found: {file_rel}')
        return ''
    return hashlib.sha256(source_path.read_bytes()).hexdigest()


def _answer_raw(value):
    return value.get('raw', '') if isinstance(value, dict) else value


def _active_fingerprint_or_raise(fingerprint):
    """Return a canonical active fingerprint or fail safely for an in-flight reservation."""
    for attempt in range(FINGERPRINT_RECHECK_ATTEMPTS):
        registry = QuestionContentFingerprint.objects.select_related(
            'canonical_question__paper'
        ).filter(fingerprint=fingerprint).first()
        if not registry:
            return None
        if (
            registry.state == QuestionContentFingerprint.State.ACTIVE
            and registry.canonical_question_id
        ):
            return registry
        if attempt < FINGERPRINT_RECHECK_ATTEMPTS - 1:
            time.sleep(FINGERPRINT_RECHECK_DELAY_SECONDS)
    raise FingerprintReservationPendingError(
        f'Fingerprint {fingerprint} remains reserved without a canonical question'
    )


def _append_duplicate_detail(details, *, source_index, category, fingerprint, registry=None):
    """Keep duplicate diagnostics bounded while retaining source-level context."""
    if len(details) >= 20:
        return
    details.append({
        'source_index': source_index,
        'category': category,
        'fingerprint': fingerprint,
        'existing_canonical_question_id': (
            str(registry.canonical_question_id) if registry and registry.canonical_question_id else None
        ),
        'existing_paper_id': (
            str(registry.canonical_question.paper_id)
            if registry and registry.canonical_question_id else None
        ),
        'summary': (
            registry.canonical_question.stem[:200]
            if registry and registry.canonical_question_id else None
        ),
    })


def _complete_duplicate_details(details):
    """Attach canonical metadata to package duplicates once the representative is active."""
    for detail in details:
        if detail['existing_canonical_question_id']:
            continue
        registry = QuestionContentFingerprint.objects.select_related(
            'canonical_question__paper'
        ).filter(
            fingerprint=detail['fingerprint'],
            state=QuestionContentFingerprint.State.ACTIVE,
        ).first()
        if registry and registry.canonical_question_id:
            detail['existing_canonical_question_id'] = str(registry.canonical_question_id)
            detail['existing_paper_id'] = str(registry.canonical_question.paper_id)
            detail['summary'] = registry.canonical_question.stem[:200]


def _cleanup_media_paths(paths):
    """Remove media copied by a failed database transaction and prune empty import folders."""
    for path in {Path(path) for path in paths}:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            logger.warning('Unable to clean failed JSON import media: %s', path)
    root = settings.MEDIA_ROOT / 'exams' / 'json_imports'
    for path in {Path(path).parent for path in paths}:
        while path != root.parent and path.is_relative_to(root):
            try:
                path.rmdir()
            except OSError:
                break
            path = path.parent


def _create_json_import_paper(paper_info, user, source_file_path):
    subject = paper_info.get('subject', '物理')
    return ExamPaper.objects.create(
        title=paper_info.get('title', 'JSON导入试卷'),
        subject=subject,
        grade=paper_info.get('grade', ''),
        stage='junior' if '年级' in str(paper_info.get('grade', '')) else 'senior',
        paper_type='json_import',
        region=paper_info.get('source_file', ''),
        source_file_path=source_file_path,
        status='reviewing',
        uploaded_by=user,
    )


def _question_error(qdata, index, exc):
    return {
        'question_no': qdata.get('question_no', f'未知(索引{index})'),
        'error': str(exc)[:200],
    }


@transaction.atomic
def _import_single_question(qdata, paper, assets_dir, base_dir, created_media_paths=None):
    """导入单道题目及其关联图片。"""
    answer_raw = _answer_raw(qdata.get('answer', ''))
    qtype = normalize_question_type(
        qdata.get('question_type', ''),
        stem=qdata.get('stem', ''),
        options=qdata.get('options') or [],
        answer=answer_raw,
    )
    raw_type = str(qdata.get('question_type', '') or '')
    source_question_type = qdata.get('source_question_type') or (
        raw_type if raw_type and raw_type != qtype else ''
    )

    # 使用字母代码生成 system_id（与现有 QuestionIDCounter 保持一致）
    system_id = generate_question_system_id(SUBJECT_LETTER_MAP.get(paper.subject, 'P'))

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
        source_question_type=source_question_type,
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
            ill,
            question,
            paper,
            assets_dir,
            image_type='diagram',
            sort_order=index,
            created_media_paths=created_media_paths,
        )

    # 导入公式图片
    formula_urls = {}
    for index, fa in enumerate(qdata.get('formula_assets', [])):
        image = _import_asset_image(
            fa,
            question,
            paper,
            assets_dir,
            image_type='formula',
            sort_order=index,
            created_media_paths=created_media_paths,
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
    asset_data,
    question,
    paper,
    assets_dir,
    image_type='other',
    sort_order=0,
    created_media_paths=None,
):
    """导入单个资源图片（插图或公式图片）。"""
    file_rel = asset_data.get('file', '')
    if not file_rel:
        raise SourceAssetNotFoundError('Image asset path is required')

    # 解析图片实际路径
    # JSON中路径如 "../assets/q01_stem.png" 或 "../assets/formula_02.png"
    asset_filename = os.path.basename(file_rel)
    src_path = assets_dir / asset_filename

    if not src_path.exists():
        raise SourceAssetNotFoundError(f'Image asset not found: {file_rel}')

    # 复制到 media 目录
    dest_dir = settings.MEDIA_ROOT / 'exams' / 'json_imports' / str(paper.id)
    dest_dir.mkdir(parents=True, exist_ok=True)

    original_dest_name = f'{question.id}_{asset_filename}'
    original_dest_path = dest_dir / original_dest_name
    if created_media_paths is not None:
        created_media_paths.append(original_dest_path)
        if image_type == 'formula':
            created_media_paths.append(original_dest_path.with_suffix('.png'))
    shutil.copy2(str(src_path), str(original_dest_path))

    display_path = original_dest_path
    if image_type == 'formula':
        display_path = convert_formula_asset(original_dest_path, original_dest_path)
        if created_media_paths is not None and display_path != original_dest_path:
            created_media_paths.append(display_path)

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
