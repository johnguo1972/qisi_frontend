import os
import re
import uuid
from datetime import timedelta
from xml.sax.saxutils import escape
from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponse, StreamingHttpResponse
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from apps.study.permissions import IsStudentOnly, IsStudentOrParentContext, IsStudentOrParentHomeContext
from rest_framework.response import Response
from apps.accounts.auth import get_request_role
from apps.missions.models import LearningMission, MissionLevel, MissionQuestionRel
from apps.study.models import StudentMissionProgress, StudentLevelProgress, AnswerAttempt
from apps.parser.models import ExamQuestion
from apps.parser.models import QuestionImage, QuestionOption
from apps.common.batch_tasks import PROGRESS_KEY_PREFIX
from apps.common.media import media_url
from apps.missions.services import assignment_levels, close_stale_missions
from apps.missions.pdf_service import _mission_questions, mission_pdf_download_url


def make_trace_id():
    return uuid.uuid4().hex[:16]


def _visible_mission_rels(level_or_mission, student_id):
    """Return relations visible to a student, including class-wide questions."""
    if isinstance(level_or_mission, MissionLevel):
        manager = MissionQuestionRel.objects.filter(level=level_or_mission)
    else:
        manager = MissionQuestionRel.objects.filter(mission=level_or_mission)
    return [rel for rel in manager if not rel.target_student_ids or str(student_id) in {str(value) for value in rel.target_student_ids}]


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsStudentOrParentHomeContext])
def student_home(request):
    """S-01: Student home - task list.

    Query params:
        class_id: filter missions by class ID (optional)
        scope: date filter — 'today' (end_at covers today) or 'week' (end_at within 7 days)
    """
    from apps.institutions.models import ClassStudent
    close_stale_missions()
    student = getattr(request, '_effective_student', request.user)

    # 获取学生所在的班级ID列表
    student_class_ids = set(
        ClassStudent.objects.filter(
            student=student, status='active',
        ).values_list('class_obj_id', flat=True)
    )

    classes = list(
        ClassStudent.objects.filter(student=student, status='active')
        .select_related('class_obj')
        .values('class_obj_id', 'class_obj__class_name')
    )

    if not student_class_ids:
        return Response({
            'code': 0, 'message': 'success', 'data': {'missions': [], 'classes': classes}, 'trace_id': make_trace_id(),
        })

    # 获取已发布的任务（属于学生所在班级的）
    published_missions = LearningMission.objects.filter(
        status='published',
        class_obj_id__in=student_class_ids,
    ).select_related('class_obj').order_by('-created_at')

    # 自动为缺失的任务创建进度记录
    existing_progress_ids = set(
        StudentMissionProgress.objects.filter(
            student_user_id=student
        ).values_list('mission_id', flat=True)
    )
    to_create = []
    for mission in published_missions:
        if mission.id not in existing_progress_ids:
            to_create.append(StudentMissionProgress(
                mission=mission,
                student_user_id=student,
                progress_status='not_started',
                progress_percent=0,
            ))
    if to_create and get_request_role(request) == 'student':
        StudentMissionProgress.objects.bulk_create(to_create)

    # 查询进度记录（现在一定包含了所有已发布的任务）
    progresses = StudentMissionProgress.objects.filter(
        student_user_id=student
    ).select_related('mission', 'mission__class_obj')

    class_id = request.query_params.get('class_id')
    # 前端“全部班级”使用 0 作为占位值，将其视为不筛选班级；真实班级 ID 仍必须是 UUID。
    if class_id and str(class_id) != '0':
        try:
            class_uuid = uuid.UUID(str(class_id))
        except (ValueError, TypeError, AttributeError):
            return Response({
                'code': 400, 'message': 'class_id must be a valid UUID',
                'data': None, 'trace_id': make_trace_id(),
            }, status=400)
        progresses = progresses.filter(mission__class_obj_id=class_uuid)

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
        visible_levels = assignment_levels(mission)
        level_count = len(visible_levels)
        question_count = len(_visible_mission_rels(mission, student.id))

        # 实时计算各关卡进度，取平均值作为任务整体进度
        levels = visible_levels
        total_progress = 0
        for lv in levels:
            level_q_count = len(_visible_mission_rels(lv, student.id))
            correct_count = AnswerAttempt.objects.filter(
                student_user_id=student,
                level=lv,
                is_correct=True,
            ).values('question_id').distinct().count()
            level_pct = round(correct_count / max(level_q_count, 1) * 100, 0) if level_q_count > 0 else 0
            total_progress += level_pct
        overall_progress = round(total_progress / max(level_count, 1), 2)

        # 同步更新数据库
        if get_request_role(request) == 'student':
            p.progress_percent = overall_progress
            if overall_progress >= 100:
                p.progress_status = 'completed'
            elif overall_progress > 0:
                p.progress_status = 'in_progress'
            p.save(update_fields=['progress_percent', 'progress_status'])

        missions.append({
            'mission': {
                'id': mission.id,
                'mission_no': mission.mission_no,
                'mission_name': mission.mission_name,
            },
            'class_label': class_obj.class_name if class_obj else None,
            'deadline': mission.end_at.isoformat() if mission.end_at else None,
            'assignment_mode': mission.assignment_mode,
            'level_count': level_count,
            'question_count': question_count,
            'progress_status': p.progress_status,
            'progress_percent': float(overall_progress),
            'current_level_id': p.current_level_id,
            'pdf_download_url': mission_pdf_download_url(mission),
        })

    return Response({
        'code': 0, 'message': 'success', 'data': {'missions': missions, 'classes': classes}, 'trace_id': make_trace_id(),
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsStudentOrParentContext])
def student_mission_detail(request, mission_id):
    """S-02: Student mission detail."""
    close_stale_missions()
    try:
        mission = LearningMission.objects.get(pk=mission_id)
    except LearningMission.DoesNotExist:
        return Response({'code': 404, 'message': '任务不存在或未发布', 'data': None, 'trace_id': make_trace_id()}, status=404)

    if mission.status != 'published':
        return Response({'code': 403, 'message': '任务未发布', 'data': None, 'trace_id': make_trace_id()}, status=403)

    # 校验学生有权访问（存在任务进度记录）
    if not StudentMissionProgress.objects.filter(
            mission=mission, student_user_id=request.user).exists():
        return Response({'code': 403, 'message': '无权访问该任务', 'data': None, 'trace_id': make_trace_id()}, status=403)

    levels = []
    total_progress = 0
    for lv in assignment_levels(mission):
        lp = StudentLevelProgress.objects.filter(
            level=lv, student_user_id=request.user
        ).first()
        level_q_count = len(_visible_mission_rels(lv, request.user.id))

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
        total_progress += progress_pct

    # 更新任务整体进度到数据库（供首页展示）
    level_count = max(len(levels), 1)
    overall_progress = round(total_progress / level_count, 2)
    try:
        sp = StudentMissionProgress.objects.get(
            mission=mission, student_user_id=request.user
        )
        if get_request_role(request) == 'student':
            sp.progress_percent = overall_progress
            if overall_progress >= 100:
                sp.progress_status = 'completed'
            elif sp.progress_status == 'not_started' and overall_progress > 0:
                sp.progress_status = 'in_progress'
            sp.save()
    except StudentMissionProgress.DoesNotExist:
        pass

    class_obj = mission.class_obj
    return Response({
        'code': 0, 'message': 'success',
        'data': {
            'mission_name': mission.mission_name,
            'goal_text': mission.goal_text,
            'class_name': class_obj.class_name if class_obj else None,
            'deadline': mission.end_at.isoformat() if mission.end_at else None,
            'assignment_mode': mission.assignment_mode,
            'pdf_download_url': mission_pdf_download_url(mission),
            'levels': levels,
        }, 'trace_id': make_trace_id(),
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsStudentOrParentContext])
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

    rels = _visible_mission_rels(level, request.user.id)
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
                'images': [
                    {
                        'id': img.id,
                        'file_path': img.file_path,
                        'url': media_url(img.file_path),
                        'image_type': img.image_type,
                        'display_width': img.display_width,
                        'description': img.description or '',
                    }
                    for img in q.images.all().order_by('sort_order')
                    if img.file_path and img.image_type != 'formula'
                ],
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

    # 更新任务进度状态为进行中
    if level.mission_id:
        StudentMissionProgress.objects.filter(
            mission_id=level.mission_id, student_user_id=request.user
        ).exclude(progress_status='in_progress').exclude(progress_status='completed').update(
            progress_status='in_progress',
            current_level_id=level.id,
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
@permission_classes([IsAuthenticated, IsStudentOrParentContext])
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
    type_label = (
        '精练作业' if export_type == 'practice'
        else '同类题练习' if export_type == 'variants'
        else '错题本' if export_type == 'wrongbook'
        else '任务题目'
    )
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


_LATEX_BLOCK_PATTERN = re.compile(
    r'\$\$(?P<display_dollar>[\s\S]*?)\$\$|'
    r'(?<!\$)\$(?!\$)(?P<inline>[\s\S]+?)(?<!\$)\$(?!\$)|'
    r'\\\[(?P<display_bracket>[\s\S]*?)\\\]|'
    r'\\\((?P<inline_paren>[\s\S]*?)\\\)'
)

_LATEX_SYMBOLS = {
    'alpha': 'α', 'beta': 'β', 'gamma': 'γ', 'delta': 'δ',
    'epsilon': 'ε', 'theta': 'θ', 'lambda': 'λ', 'mu': 'μ',
    'pi': 'π', 'sigma': 'σ', 'phi': 'φ', 'omega': 'ω',
    'times': '×', 'cdot': '·', 'div': '÷', 'pm': '±',
    'le': '≤', 'leq': '≤', 'ge': '≥', 'geq': '≥',
    'neq': '≠', 'ne': '≠', 'approx': '≈', 'infty': '∞',
    'rightarrow': '→', 'leftarrow': '←', 'Rightarrow': '⇒',
    'Leftarrow': '⇐', 'to': '→', 'in': '∈', 'notin': '∉',
    'subset': '⊂', 'supset': '⊃', 'cup': '∪', 'cap': '∩',
    'parallel': '∥', 'perp': '⊥', 'angle': '∠', 'triangle': '△',
    'sqrt': '√',
}


def _latex_to_reportlab(formula: str) -> str:
    """Convert common LaTeX math to safe ReportLab paragraph markup."""
    formula = str(formula or '')
    # Accept both normal LaTeX and JSON-escaped values from imported papers.
    formula = formula.replace('\\\\', '\\')

    def read_argument(text, position):
        while position < len(text) and text[position].isspace():
            position += 1
        if position >= len(text):
            return '', position
        if text[position] == '{':
            return read_sequence(text, position + 1, stop='}')
        return read_atom(text, position)

    def read_atom(text, position):
        if position >= len(text):
            return '', position
        if text[position] == '{':
            return read_sequence(text, position + 1, stop='}')
        if text[position] == '\\':
            return read_command(text, position + 1)
        return escape(text[position]), position + 1

    def read_command(text, position):
        if position >= len(text):
            return '', position
        if text[position].isalpha():
            start = position
            while position < len(text) and text[position].isalpha():
                position += 1
            name = text[start:position]
        else:
            name = text[position]
            position += 1

        if name in {'mathrm', 'mathbf', 'mathit', 'text', 'textrm', 'operatorname'}:
            return read_argument(text, position)
        if name == 'underline':
            value, position = read_argument(text, position)
            return f'<u>{value}</u>', position
        if name in {'frac', 'dfrac', 'tfrac'}:
            numerator, position = read_argument(text, position)
            denominator, position = read_argument(text, position)
            return f'({numerator})/({denominator})', position
        if name == 'sqrt':
            if position < len(text) and text[position] == '[':
                closing = text.find(']', position + 1)
                position = len(text) if closing < 0 else closing + 1
            value, position = read_argument(text, position)
            return f'√({value})', position
        if name == 'hspace':
            value, position = read_argument(text, position)
            match = re.search(r'(\d+(?:\.\d+)?)', re.sub(r'<[^>]+>', '', value))
            count = max(3, min(12, round(float(match.group(1)) * 4))) if match else 5
            return '_' * count, position
        if name in {'left', 'right', 'displaystyle', 'textstyle', 'limits'}:
            return '', position
        if name in {'quad', 'qquad', ',', ';', '!', ':'}:
            return ' ', position
        if name in _LATEX_SYMBOLS:
            return escape(_LATEX_SYMBOLS[name]), position
        return escape(name), position

    def read_sequence(text, position, stop=None):
        result = []
        while position < len(text):
            char = text[position]
            if stop and char == stop:
                return ''.join(result), position + 1
            if char == '\\':
                value, position = read_command(text, position + 1)
                result.append(value)
                continue
            if char in '^_':
                value, position = read_atom(text, position + 1)
                tag = 'super' if char == '^' else 'sub'
                result.append(f'<{tag}>{value}</{tag}>')
                continue
            if char == '{':
                value, position = read_sequence(text, position + 1, stop='}')
                result.append(value)
                continue
            result.append(' ' if char == '~' else escape(char))
            position += 1
        return ''.join(result), position

    return read_sequence(formula, 0)[0]


def _pdf_text_with_formulas(value: object) -> str:
    """Escape normal text and convert embedded math delimiters."""
    from xml.sax.saxutils import escape

    text = str(value or '')
    result = []
    position = 0
    for match in _LATEX_BLOCK_PATTERN.finditer(text):
        result.append(escape(text[position:match.start()]))
        groups = match.groupdict()
        formula = next(content for content in groups.values() if content is not None)
        is_display = groups['display_dollar'] is not None or groups['display_bracket'] is not None
        rendered = _latex_to_reportlab(formula.strip())
        result.append(f'<br/>{rendered}<br/>' if is_display else rendered)
        position = match.end()
    result.append(escape(text[position:]))
    return ''.join(result)


def _export_question_type(q: dict, infer_unknown: bool = False) -> str:
    """Return a displayable type, inferring legacy ``unknown`` questions."""
    question_type = str(q.get('question_type') or '').strip().lower()
    if not infer_unknown or question_type not in {'', 'unknown'}:
        return question_type

    stem = str(q.get('stem') or '').replace('\\\\', '\\')
    if re.search(r'选填|填空|\\underline|_{2,}', stem, re.IGNORECASE):
        return 'fill_blank'

    options = q.get('options_html') or q.get('options') or []
    if options or re.search(r'\\mathrm\s*\{[A-D]\}|(?:^|[\n])\s*[A-D][.．、]', stem, re.IGNORECASE):
        answer = str(q.get('answer') or '').upper()
        answer_letters = re.findall(r'(?<![A-Z])[A-D](?![A-Z])', answer)
        return 'multiple_choice' if len(set(answer_letters)) > 1 else 'single_choice'
    return 'unknown'


def _build_pdf(export_type: str, questions: list, include_answers: bool,
               watermark_text: str = "", render_formulas: bool = False) -> bytes:
    """增强版 PDF 生成：水印、知识点标签、页码、图片。"""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                     Image as RLImage, PageTemplate, Frame,
                                     Table, TableStyle)
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    from xml.sax.saxutils import escape
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
    question_number = ParagraphStyle('ZhQuestionNumber', parent=body,
                                     fontSize=9, leading=14)
    h1 = ParagraphStyle('ZhH1', parent=styles['Title'],
                        fontName='STSong-Light', fontSize=18)
    story = []

    def pdf_text(value):
        """Escape user/imported text before passing it to ReportLab Paragraph."""
        return escape(str(value or ''))

    content_text = _pdf_text_with_formulas if render_formulas else pdf_text

    def option_text(option, index):
        """Accept both API-shaped options and raw QuestionOption values."""
        if not isinstance(option, dict):
            return chr(65 + index), str(option or '')
        label = option.get('label') or option.get('option_label') or chr(65 + index)
        content = option.get('content')
        if content is None:
            content = option.get('text', '')
        return str(label), str(content or '')

    type_label = '同类题练习' if export_type == 'variants' else ('错题本' if export_type == 'wrongbook' else '任务题目')
    type_label = next(
        (str(q.get('_pdf_title')) for q in questions if q.get('_pdf_title')),
        type_label,
    )
    story.append(Paragraph(pdf_text(type_label), h1))
    story.append(Spacer(1, 6*mm))
    story.append(Paragraph(f'导出时间：{timezone.now().strftime("%Y-%m-%d %H:%M:%S")}　题目数：{len(questions)}', body))
    story.append(Spacer(1, 6*mm))

    # Only short-answer questions reserve handwritten answer space. Choice,
    # true/false and fill-in-the-blank questions keep the compact layout.
    short_answer_types = {'short_answer'}
    for i, q in enumerate(questions, 1):
        effective_type = _export_question_type(q, infer_unknown=render_formulas)
        qtype = ExamQuestion.QUESTION_TYPE_LABELS.get(effective_type, '未识别题型' if render_formulas else effective_type)
        header_label = f'第{i}题（{qtype}）'
        header_width = max(
            15 * mm,
            pdfmetrics.stringWidth(header_label, 'STSong-Light', question_number.fontSize) + 6,
        )
        question_header = Table([
            [
                Paragraph(pdf_text(header_label), question_number),
                Paragraph(content_text(q.get('stem')), body),
            ]
        ], colWidths=[header_width, doc.width - header_width])
        question_header.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ]))
        story.append(question_header)

        # 知识点标签
        kps = q.get('knowledge_points') or []
        if kps:
            kp_text = "知识点：" + "、".join(
                pdf_text(kp.get('module', '') if isinstance(kp, dict) else str(kp))
                for kp in kps[:3]
            )
            story.append(Paragraph(f'<font color="#666666" size="9">{kp_text}</font>', body))

        image_items = q.get('image_items') or [
            {'file_path': img_url, 'placement': 'stem'}
            for img_url in q.get('image_urls', [])
        ]

        def append_images(items):
            for item in items:
                img_url = item.get('file_path') if isinstance(item, dict) else item
                if not img_url:
                    continue
                img_path = str(img_url)
                if not os.path.isabs(img_path):
                    img_path = str(settings.MEDIA_ROOT / img_path.lstrip('/'))
                if img_path.startswith(('http://', 'https://')):
                    continue
                img_path = os.path.normpath(img_path)
                if not os.path.exists(img_path):
                    continue
                try:
                    image_width, image_height = ImageReader(img_path).getSize()
                    max_width, max_height = doc.width, 100 * mm
                    requested_width = item.get('display_width') if isinstance(item, dict) else None
                    if requested_width:
                        max_width = min(max_width, float(requested_width) * mm)
                    scale = min(max_width / image_width, max_height / image_height, 1)
                    story.append(Spacer(1, 2 * mm))
                    story.append(RLImage(img_path, width=image_width * scale,
                                         height=image_height * scale))
                    story.append(Spacer(1, 2 * mm))
                except Exception:
                    pass

        stem_images = [
            item for item in image_items
            if (item.get('placement') if isinstance(item, dict) else 'stem') != 'options'
        ]
        option_images = [
            item for item in image_items
            if (item.get('placement') if isinstance(item, dict) else 'stem') == 'options'
        ]
        append_images(stem_images)

        for option_index, opt in enumerate(q.get('options_html', [])):
            label, content = option_text(opt, option_index)
            story.append(Paragraph(f'{pdf_text(label)}. {content_text(content)}', body))
        append_images(option_images)

        if include_answers:
            if q.get('answer'):
                story.append(Paragraph(f'<b>答案：</b>{content_text(q["answer"])}', body))
            if q.get('analysis'):
                story.append(Paragraph(f'<b>解析：</b>{content_text(q["analysis"])}', body))
        story.append(Spacer(1, 4*mm))
        if q.get('question_type') in short_answer_types:
            story.append(Spacer(1, 50*mm))

    doc.build(story)
    return buf.getvalue()


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsStudentOnly])
def export_pdf(request):
    """导出错题本、同类题或任务题目为 PDF。

    Request body:
        export_type: 'wrongbook' | 'variants' | 'mission'
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
    source_wrong_item_id = request.data.get('source_wrong_item_id')
    include_answers = request.data.get('include_answers', False)
    watermark_text = request.data.get('watermark_text', '')

    if export_type not in ('wrongbook', 'variants', 'mission'):
        return Response({
            'code': 400, 'message': 'export_type 必须为 wrongbook、variants 或 mission', 'data': None, 'trace_id': trace_id,
        }, status=400)
    if not item_ids or not isinstance(item_ids, list):
        return Response({
            'code': 400, 'message': 'item_ids 必须是非空列表', 'data': None, 'trace_id': trace_id,
        }, status=400)

    # --- fetch questions ---
    questions_data = []
    render_export_type = export_type
    if export_type in ('wrongbook', 'variants'):
        from apps.wrongbook.models import WrongBookItem
        from apps.wrongbook.services import find_variant_questions
        if export_type == 'wrongbook':
            items = WrongBookItem.objects.filter(
                student_user_id=request.user, question_id__in=item_ids
            ).values_list('question_id', flat=True)
            export_question_ids = [str(question_id) for question_id in items]
            # Backward compatibility for an already-opened old variants page:
            # it sent variant question IDs while declaring export_type=wrongbook.
            # If none are original wrong-book questions, authorize the IDs
            # against this student's variant candidates instead of returning a
            # false 404. Valid original wrong-book export behavior is unchanged.
            if not export_question_ids:
                allowed_ids = set()
                for original_id in WrongBookItem.objects.filter(
                    student_user_id=request.user,
                ).values_list('question_id', flat=True):
                    allowed_ids.update(
                        str(question.get('id'))
                        for question in find_variant_questions(original_id, limit=3)
                    )
                export_question_ids = [
                    str(question_id) for question_id in item_ids
                    if str(question_id) in allowed_ids
                ]
                if export_question_ids:
                    render_export_type = 'variants'
        else:
            # The legacy variants page sends recommended question IDs, not
            # WrongBookItem IDs. Re-run recommendation and authorize only
            # questions belonging to this student's selected wrong item.
            source_item = WrongBookItem.objects.filter(
                pk=source_wrong_item_id, student_user_id=request.user,
            ).first()
            if source_item is not None:
                allowed_ids = {
                    str(question.get('id'))
                    for question in find_variant_questions(source_item.question_id, limit=3)
                }
            else:
                # New clients normally send source_wrong_item_id.  The
                # fallback keeps old deep links functional while still
                # authorizing only candidates of the current student.
                allowed_ids = set()
                for original_id in WrongBookItem.objects.filter(
                    student_user_id=request.user,
                ).values_list('question_id', flat=True):
                    allowed_ids.update(
                        str(question.get('id'))
                        for question in find_variant_questions(original_id, limit=3)
                    )
            export_question_ids = [
                str(question_id) for question_id in item_ids
                if str(question_id) in allowed_ids
            ]

        qs = ExamQuestion.objects.filter(id__in=export_question_ids).values(
            'id', 'question_no', 'question_type', 'stem', 'stem_html',
            'answer', 'analysis', 'knowledge_points',
        )
        question_map = {str(question['id']): question for question in qs}
        for question_id in export_question_ids:
            q = question_map.get(question_id)
            if q is None:
                continue
            options = list(QuestionOption.objects.filter(question_id=q['id']).values(
                'option_label', 'content'
            ).order_by('sort_order'))
            images = list(QuestionImage.objects.filter(
                question_id=q['id'],
            ).exclude(image_type='formula').values('file_path').order_by('sort_order'))
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
        visible_ids = {
            str(rel.question_id)
            for rel in _visible_mission_rels(mission, request.user.id)
        }
        # Reuse the mission relation order instead of relying on an unordered
        # question_id__in query.
        questions_data = [
            question for question in _mission_questions(mission)
            if str(question['id']) in visible_ids
        ]

    if not questions_data:
        return Response({
            'code': 404, 'message': '未找到可导出的题目', 'data': None, 'trace_id': trace_id,
        }, status=404)

    # --- generate file ---
    questions_data = questions_data[:50]  # max 50 题/PDF
    export_dir = os.path.join(settings.MEDIA_ROOT, 'exports')
    os.makedirs(export_dir, exist_ok=True)
    filename = f'{render_export_type}_{uuid.uuid4().hex[:12]}.pdf'
    filepath = os.path.join(export_dir, filename)

    if render_export_type == 'variants':
        pdf_bytes = _build_pdf(
            render_export_type, questions_data, include_answers, watermark_text,
            render_formulas=True,
        )
    else:
        pdf_bytes = _build_pdf(render_export_type, questions_data, include_answers, watermark_text)
    with open(filepath, 'wb') as f:
        f.write(pdf_bytes)

    download_url = f'{settings.MEDIA_URL}exports/{filename}'

    return Response({
        'code': 0, 'message': '导出成功',
        'data': {'download_url': download_url, 'question_count': len(questions_data)},
        'trace_id': trace_id,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsStudentOnly])
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
