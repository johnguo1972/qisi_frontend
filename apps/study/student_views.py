import os
import uuid
from datetime import timedelta
from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponse, StreamingHttpResponse
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from apps.study.permissions import IsStudent
from rest_framework.response import Response
from apps.missions.models import LearningMission, MissionLevel, MissionQuestionRel
from apps.study.models import StudentMissionProgress, StudentLevelProgress, AnswerAttempt
from apps.parser.models import ExamQuestion
from apps.parser.models import QuestionImage, QuestionOption
from apps.common.batch_tasks import PROGRESS_KEY_PREFIX


def make_trace_id():
    return uuid.uuid4().hex[:16]


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsStudent])
def student_home(request):
    """S-01: Student home - task list.

    Query params:
        class_id: filter missions by class ID (optional)
        scope: date filter — 'today' (end_at covers today) or 'week' (end_at within 7 days)
    """
    from apps.institutions.models import ClassStudent

    # 获取学生所在的班级ID列表
    student_class_ids = set(
        ClassStudent.objects.filter(
            student=request.user, status='active',
        ).values_list('class_obj_id', flat=True)
    )

    if not student_class_ids:
        return Response({
            'code': 0, 'message': 'success', 'data': {'missions': []}, 'trace_id': make_trace_id(),
        })

    # 获取已发布的任务（属于学生所在班级的）
    published_missions = LearningMission.objects.filter(
        status='published',
        class_obj_id__in=student_class_ids,
    ).select_related('class_obj').order_by('-created_at')

    # 自动为缺失的任务创建进度记录
    existing_progress_ids = set(
        StudentMissionProgress.objects.filter(
            student_user_id=request.user
        ).values_list('mission_id', flat=True)
    )
    to_create = []
    for mission in published_missions:
        if mission.id not in existing_progress_ids:
            to_create.append(StudentMissionProgress(
                mission=mission,
                student_user_id=request.user,
                progress_status='not_started',
                progress_percent=0,
            ))
    if to_create:
        StudentMissionProgress.objects.bulk_create(to_create)

    # 查询进度记录（现在一定包含了所有已发布的任务）
    progresses = StudentMissionProgress.objects.filter(
        student_user_id=request.user
    ).select_related('mission', 'mission__class_obj')

    class_id = request.query_params.get('class_id')
    if class_id and int(class_id) > 0:
        progresses = progresses.filter(mission__class_obj_id=class_id)

    # Filter by scope (date range on end_at)
    scope = request.query_params.get('scope')
    now = timezone.now()
    if scope == 'today':
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)
        progresses = progresses.filter(mission__end_at__gte=today_start, mission__end_at__lt=today_end)
    elif scope == 'week':
        week_end = now + timedelta(days=7)
        progresses = progresses.filter(mission__end_at__lte=week_end)

    missions = []
    for p in progresses:
        mission = p.mission
        class_obj = mission.class_obj
        level_count = mission.levels.count()
        question_count = MissionQuestionRel.objects.filter(mission=mission).count()
        missions.append({
            'mission': {
                'id': mission.id,
                'mission_no': mission.mission_no,
                'mission_name': mission.mission_name,
            },
            'class_label': class_obj.class_name if class_obj else None,
            'deadline': mission.end_at.isoformat() if mission.end_at else None,
            'level_count': level_count,
            'question_count': question_count,
            'progress_status': p.progress_status,
            'progress_percent': float(p.progress_percent) if p.progress_percent is not None else 0,
            'current_level_id': p.current_level_id,
        })

    return Response({
        'code': 0, 'message': 'success', 'data': {'missions': missions}, 'trace_id': make_trace_id(),
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsStudent])
def student_mission_detail(request, mission_id):
    """S-02: Student mission detail."""
    try:
        mission = LearningMission.objects.get(pk=mission_id, status='published')
    except LearningMission.DoesNotExist:
        return Response({'code': 404, 'message': '任务不存在或未发布', 'data': None, 'trace_id': make_trace_id()}, status=404)

    # 校验学生有权访问（存在任务进度记录）
    if not StudentMissionProgress.objects.filter(
            mission=mission, student_user_id=request.user).exists():
        return Response({'code': 403, 'message': '无权访问该任务', 'data': None, 'trace_id': make_trace_id()}, status=403)

    levels = []
    for lv in mission.levels.all():
        lp = StudentLevelProgress.objects.filter(
            level=lv, student_user_id=request.user
        ).first()
        level_q_count = MissionQuestionRel.objects.filter(level=lv).count()

        # 计算关卡进度：已答对的题目数 / 总题目数
        correct_count = AnswerAttempt.objects.filter(
            student_user_id=request.user,
            level=lv,
            is_correct=True,
        ).values('question_id').distinct().count()
        progress_pct = round(correct_count / max(level_q_count, 1) * 100, 0) if level_q_count > 0 else 0

        levels.append({
            'id': lv.id, 'level_no': lv.level_no, 'level_name': lv.level_name,
            'level_type': lv.level_type,
            'status': lp.status if lp else 'locked',
            'question_count': level_q_count,
            'progress_percent': progress_pct,
        })

    class_obj = mission.class_obj
    return Response({
        'code': 0, 'message': 'success',
        'data': {
            'mission_name': mission.mission_name,
            'goal_text': mission.goal_text,
            'class_name': class_obj.class_name if class_obj else None,
            'deadline': mission.end_at.isoformat() if mission.end_at else None,
            'levels': levels,
        }, 'trace_id': make_trace_id(),
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsStudent])
def student_level_detail(request, level_id):
    """S-03: Current level detail with questions."""
    try:
        level = MissionLevel.objects.get(pk=level_id)
    except MissionLevel.DoesNotExist:
        return Response({'code': 404, 'message': '关卡不存在', 'data': None, 'trace_id': make_trace_id()}, status=404)

    # 校验该关卡所属任务学生有权访问
    if level.mission_id and not StudentMissionProgress.objects.filter(
            mission_id=level.mission_id, student_user_id=request.user).exists():
        return Response({'code': 403, 'message': '无权访问该关卡', 'data': None, 'trace_id': make_trace_id()}, status=403)

    rels = MissionQuestionRel.objects.filter(level=level)
    questions = []
    for rel in rels:
        try:
            q = ExamQuestion.objects.get(pk=rel.question_id)
            questions.append({
                'id': q.id,
                'question_no': q.question_no,
                'question_type': q.question_type,
                'difficulty': float(q.difficulty) if q.difficulty else None,
                'stem': q.stem or '',
                'stem_html': q.stem_html or '',
                'answer': q.answer or '',
                'analysis': q.analysis or '',
                'solution': q.solution or '',
                'images': [{'id': img.id, 'file_path': img.file_path, 'url': img.file_path} for img in q.images.all()],
                'options': [{'label': o.option_label, 'content': o.content}
                           for o in q.options.all()],
            })
        except ExamQuestion.DoesNotExist:
            continue

    # Create progress if not exists
    lp, _ = StudentLevelProgress.objects.get_or_create(
        level=level, student_user_id=request.user,
        defaults={'status': 'running'}
    )

    return Response({
        'code': 0, 'message': 'success',
        'data': {
            'level_id': level.id,
            'level_name': level.level_name,
            'mode_policy': level.mode_policy,
            'questions': questions,
            'progress': {'attempt_count': lp.attempt_count, 'status': lp.status},
        }, 'trace_id': make_trace_id(),
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsStudent])
def growth_summary(request):
    """S-12: Growth summary."""
    from apps.wrongbook.models import WrongBookItem, MasteryRecord

    base = AnswerAttempt.objects.filter(student_user_id=request.user)
    total_attempts = base.exclude(is_subjective_pending=True).count()   # 排除待批阅
    total_correct = base.filter(is_correct=True).count()
    mastered_count = MasteryRecord.objects.filter(
        student_user_id=request.user, mastery_status='mastered'
    ).count()
    wrong_count = WrongBookItem.objects.filter(
        student_user_id=request.user
    ).count()

    return Response({
        'code': 0, 'message': 'success',
        'data': {
            'total_attempts': total_attempts,
            'total_correct': total_correct,
            'accuracy': round(total_correct / max(total_attempts, 1) * 100, 1),
            'mastered_count': mastered_count,
            'wrong_book_count': wrong_count,
        },
        'trace_id': make_trace_id(),
    })


EXPORT_RATE_KEY = 'export_pdf_rate'
EXPORT_RATE_WINDOW = 3600  # 1 hour
EXPORT_RATE_LIMIT = 3


def _check_export_rate(user_id: int) -> bool:
    """Return True if within rate limit."""
    key = f'{EXPORT_RATE_KEY}:{user_id}'
    count = cache.get(key, 0)
    if count >= EXPORT_RATE_LIMIT:
        return False
    cache.set(key, count + 1, EXPORT_RATE_WINDOW)
    return True


def _build_html(export_type: str, questions: list, include_answers: bool) -> str:
    """Build a simple HTML page as PDF placeholder."""
    type_label = '错题本' if export_type == 'wrongbook' else '任务题目'
    rows = []
    for i, q in enumerate(questions, 1):
        qtype = ExamQuestion.QUESTION_TYPE_LABELS.get(q['question_type'], q['question_type'])
        rows.append(f'<h3>第{i}题（{qtype}）</h3>')
        rows.append(f'<p>{q["stem_html"] or q["stem"]}</p>')
        if q.get('options_html'):
            rows.append('<ul>')
            for opt in q['options_html']:
                rows.append(f'<li><b>{opt["label"]}.</b> {opt["content"]}</li>')
            rows.append('</ul>')
        if include_answers and q.get('answer'):
            rows.append(f'<p><b>答案：</b>{q["answer"]}</p>')
        if include_answers and q.get('analysis'):
            rows.append(f'<p><b>解析：</b>{q["analysis"]}</p>')

    return f'''<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>{type_label}导出</title>
<style>
body {{ font-family: "Microsoft YaHei", sans-serif; max-width: 800px; margin: 2em auto; padding: 0 1em; }}
h1 {{ text-align: center; }}
h3 {{ border-bottom: 1px solid #ccc; padding-bottom: 0.3em; }}
img {{ max-width: 100%; }}
</style></head><body>
<h1>{type_label}</h1>
<p>导出时间：{timezone.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
<p>题目数量：{len(questions)}</p>
{"<hr/>" + "".join(rows)}
</body></html>'''


def _build_pdf(export_type: str, questions: list, include_answers: bool,
               watermark_text: str = "") -> bytes:
    """增强版 PDF 生成：水印、知识点标签、页码、图片。"""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                     Image as RLImage, PageTemplate, Frame)
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    import io

    pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light'))
    buf = io.BytesIO()

    # 使用 onPage 回调实现水印和页码（比子类化 afterPage 更可靠）
    def on_page(canvas, doc):
        if watermark_text:
            canvas.saveState()
            canvas.setFont('STSong-Light', 40)
            canvas.setFillColor(colors.Color(0, 0, 0, alpha=0.08))
            canvas.rotate(45)
            canvas.drawString(200, -200, watermark_text)
            canvas.restoreState()
        # 页码
        canvas.saveState()
        canvas.setFont('STSong-Light', 9)
        canvas.setFillColorRGB(0.5, 0.5, 0.5)
        canvas.drawCentredString(A4[0] / 2, 15 * mm, f'- {doc.page} -')
        canvas.restoreState()

    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        topMargin=15*mm, bottomMargin=20*mm,
        leftMargin=15*mm, rightMargin=15*mm,
    )
    # 应用 onPage 回调
    frame = Frame(
        doc.leftMargin, doc.bottomMargin,
        doc.width, doc.height,
        id='normal'
    )
    doc.addPageTemplates([
        PageTemplate(frames=[frame], onPage=on_page),
    ])

    styles = getSampleStyleSheet()
    body = ParagraphStyle('ZhBody', parent=styles['Normal'],
                          fontName='STSong-Light', fontSize=11, leading=18)
    h1 = ParagraphStyle('ZhH1', parent=styles['Title'],
                        fontName='STSong-Light', fontSize=18)
    story = []

    type_label = '错题本' if export_type == 'wrongbook' else '任务题目'
    story.append(Paragraph(type_label, h1))
    story.append(Spacer(1, 6*mm))
    story.append(Paragraph(f'导出时间：{timezone.now().strftime("%Y-%m-%d %H:%M:%S")}　题目数：{len(questions)}', body))
    story.append(Spacer(1, 6*mm))

    for i, q in enumerate(questions, 1):
        qtype = ExamQuestion.QUESTION_TYPE_LABELS.get(q['question_type'], q['question_type'])
        story.append(Paragraph(f'第{i}题（{qtype}）', body))

        # 知识点标签
        kps = q.get('knowledge_points') or []
        if kps:
            kp_text = "知识点：" + "、".join(
                kp.get('module', '') if isinstance(kp, dict) else str(kp)
                for kp in kps[:3]
            )
            story.append(Paragraph(f'<font color="#666666" size="9">{kp_text}</font>', body))

        story.append(Paragraph(q['stem'] or '', body))
        for opt in q.get('options_html', []):
            story.append(Paragraph(f'{opt["label"]}. {opt["content"]}', body))

        # 图片
        for img_url in q.get('image_urls', []):
            img_path = str(settings.MEDIA_ROOT / img_url)
            if os.path.exists(img_path):
                try:
                    img = RLImage(img_path, width=400, height=200)
                    story.append(img)
                except Exception:
                    pass

        if include_answers:
            if q.get('answer'):
                story.append(Paragraph(f'<b>答案：</b>{q["answer"]}', body))
            if q.get('analysis'):
                story.append(Paragraph(f'<b>解析：</b>{q["analysis"]}', body))
        story.append(Spacer(1, 4*mm))

    doc.build(story)
    return buf.getvalue()


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsStudent])
def export_pdf(request):
    """导出错题本或任务题目为 PDF（当前返回 HTML 占位，待 reportlab 可用后替换）。

    Request body:
        export_type: 'wrongbook' | 'mission'
        item_ids: list of question IDs (for wrongbook) or mission ID (for mission, single int)
        include_answers: bool (default false)
    """
    trace_id = make_trace_id()

    # --- rate limit ---
    if not _check_export_rate(request.user.id):
        return Response({
            'code': 429, 'message': '导出过于频繁，请稍后再试', 'data': None, 'trace_id': trace_id,
        }, status=429)

    export_type = request.data.get('export_type')
    item_ids = request.data.get('item_ids')
    include_answers = request.data.get('include_answers', False)
    watermark_text = request.data.get('watermark_text', '')

    if export_type not in ('wrongbook', 'mission'):
        return Response({
            'code': 400, 'message': 'export_type 必须为 wrongbook 或 mission', 'data': None, 'trace_id': trace_id,
        }, status=400)
    if not item_ids or not isinstance(item_ids, list):
        return Response({
            'code': 400, 'message': 'item_ids 必须是非空列表', 'data': None, 'trace_id': trace_id,
        }, status=400)

    # --- fetch questions ---
    questions_data = []
    if export_type == 'wrongbook':
        from apps.wrongbook.models import WrongBookItem
        items = WrongBookItem.objects.filter(
            student_user_id=request.user, question_id__in=item_ids
        ).values_list('question_id', flat=True)
        qs = ExamQuestion.objects.filter(id__in=list(items)).values(
            'id', 'question_no', 'question_type', 'stem', 'stem_html',
            'answer', 'analysis', 'knowledge_points',
        )
        for q in qs:
            options = list(QuestionOption.objects.filter(question_id=q['id']).values(
                'option_label', 'content'
            ).order_by('sort_order'))
            images = list(QuestionImage.objects.filter(question_id=q['id']).values(
                'file_path'
            ).order_by('sort_order'))
            questions_data.append({
                **q,
                'options_html': [{'label': o['option_label'], 'content': o['content']} for o in options],
                'image_urls': [img['file_path'] for img in images],
            })
    else:
        # mission: item_ids should contain a single mission id
        mission_id = item_ids[0]
        try:
            mission = LearningMission.objects.get(pk=mission_id)
        except LearningMission.DoesNotExist:
            return Response({
                'code': 404, 'message': '任务不存在', 'data': None, 'trace_id': trace_id,
            }, status=404)
        rels = MissionQuestionRel.objects.filter(mission=mission).values_list('question_id', flat=True)
        qs = ExamQuestion.objects.filter(id__in=list(rels)).values(
            'id', 'question_no', 'question_type', 'stem', 'stem_html',
            'answer', 'analysis', 'knowledge_points',
        )
        for q in qs:
            options = list(QuestionOption.objects.filter(question_id=q['id']).values(
                'option_label', 'content'
            ).order_by('sort_order'))
            images = list(QuestionImage.objects.filter(question_id=q['id']).values(
                'file_path'
            ).order_by('sort_order'))
            questions_data.append({
                **q,
                'options_html': [{'label': o['option_label'], 'content': o['content']} for o in options],
                'image_urls': [img['file_path'] for img in images],
            })

    if not questions_data:
        return Response({
            'code': 404, 'message': '未找到可导出的题目', 'data': None, 'trace_id': trace_id,
        }, status=404)

    # --- generate file ---
    questions_data = questions_data[:50]  # max 50 题/PDF
    export_dir = os.path.join(settings.MEDIA_ROOT, 'exports')
    os.makedirs(export_dir, exist_ok=True)
    filename = f'{export_type}_{uuid.uuid4().hex[:12]}.pdf'
    filepath = os.path.join(export_dir, filename)

    pdf_bytes = _build_pdf(export_type, questions_data, include_answers, watermark_text)
    with open(filepath, 'wb') as f:
        f.write(pdf_bytes)

    download_url = f'{settings.MEDIA_URL}exports/{filename}'

    return Response({
        'code': 0, 'message': '导出成功',
        'data': {'download_url': download_url, 'question_count': len(questions_data)},
        'trace_id': trace_id,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsStudent])
def upload_attempt_image(request, attempt_id):
    """Upload a photo for a student's answer attempt.

    Accepts multipart/form-data with an 'image' file field.
    Validates the attempt belongs to the current student, saves the image
    under media/student_attempts/{attempt_id}/, and returns the accessible URL.
    """
    trace_id = make_trace_id()

    # Validate ownership
    try:
        attempt = AnswerAttempt.objects.get(
            pk=attempt_id, student_user_id=request.user
        )
    except AnswerAttempt.DoesNotExist:
        return Response({
            'code': 404, 'message': '作答记录不存在', 'data': None, 'trace_id': trace_id,
        }, status=404)

    image = request.FILES.get('image')
    if not image:
        return Response({
            'code': 400, 'message': '请提供 image 文件', 'data': None, 'trace_id': trace_id,
        }, status=400)

    # Validate file type
    allowed = {'image/jpeg', 'image/png', 'image/webp', 'image/jpg'}
    if image.content_type not in allowed:
        return Response({
            'code': 400, 'message': '仅支持 JPEG/PNG/WebP 格式图片', 'data': None, 'trace_id': trace_id,
        }, status=400)

    # Save to media/student_attempts/{attempt_id}/
    upload_dir = settings.MEDIA_ROOT / 'student_attempts' / str(attempt_id)
    upload_dir.mkdir(parents=True, exist_ok=True)

    ext = os.path.splitext(image.name)[1] or '.jpg'
    filename = f'{uuid.uuid4().hex[:12]}{ext}'
    filepath = upload_dir / filename

    with open(filepath, 'wb') as dest:
        for chunk in image.chunks():
            dest.write(chunk)

    relative_path = f'student_attempts/{attempt_id}/{filename}'
    image_url = f'{settings.MEDIA_URL}{relative_path}'

    return Response({
        'code': 0, 'message': '上传成功',
        'data': {'image_url': image_url, 'filename': filename},
        'trace_id': trace_id,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def task_progress_stream(request, task_id):
    """SSE 端点：实时推送任务进度。

    使用说明：前端通过 EventSource 或 fetch + ReadableStream 消费。
    GET /api/v1/student/tasks/<task_id>/progress
    """
    import json
    import time

    def event_stream():
        last_data = None
        while True:
            progress_data = cache.get(f'{PROGRESS_KEY_PREFIX}{task_id}')
            if progress_data and progress_data != last_data:
                last_data = progress_data
                yield f'data: {progress_data}\n\n'
                try:
                    status = json.loads(progress_data).get('status')
                    if status in ('completed', 'failed', 'cancelled'):
                        break
                except (json.JSONDecodeError, TypeError):
                    pass
            # 没有新数据时，发送心跳保持连接
            else:
                yield ': heartbeat\n\n'
            time.sleep(2)

    response = StreamingHttpResponse(
        event_stream(),
        content_type='text/event-stream',
    )
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    return response
