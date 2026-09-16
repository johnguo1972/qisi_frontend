"""A4 PDF renderer for immutable classroom feedback reports."""
from __future__ import annotations

import html
import os
import re
import tempfile
from pathlib import Path

from django.conf import settings
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import (
    KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)


FONT_NAME = 'STSong-Light'
PAGE_WIDTH, PAGE_HEIGHT = A4


def _safe_name(value, fallback='反馈'):
    text = re.sub(r'[\\/:*?"<>|]+', '_', str(value or '')).strip(' ._')
    return text[:60] or fallback


def _paragraph(value, style):
    text = html.escape(str(value or '')).replace('\n', '<br/>')
    return Paragraph(text, style)


def _footer(canvas, doc):
    canvas.saveState()
    canvas.setFont(FONT_NAME, 8)
    canvas.setFillColor(colors.HexColor('#666666'))
    canvas.drawCentredString(PAGE_WIDTH / 2, 12 * mm, f'{doc.page}')
    canvas.restoreState()


def _table(data, widths, header=True):
    table = Table(data, colWidths=widths, repeatRows=1 if header else 0, hAlign='LEFT')
    commands = [
        ('GRID', (0, 0), (-1, -1), 0.35, colors.HexColor('#d9dfe7')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 7),
        ('RIGHTPADDING', (0, 0), (-1, -1), 7),
        ('TOPPADDING', (0, 0), (-1, -1), 7),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
    ]
    if header:
        commands.extend([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f3f6fa')),
            ('FONTNAME', (0, 0), (-1, 0), FONT_NAME),
        ])
    table.setStyle(TableStyle(commands))
    return table


def generate_feedback_pdf(report):
    """Render one report and return its storage-relative media path."""
    pdfmetrics.registerFont(UnicodeCIDFont(FONT_NAME))
    relative = f"exports/classroom_feedback/{report.id}/课堂反馈-{_safe_name(report.mission.mission_name)}-{_safe_name(report.class_obj.class_name)}.pdf"
    output = Path(settings.MEDIA_ROOT) / relative
    output.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='classroom-feedback-', suffix='.pdf', dir=output.parent)
    os.close(fd)
    styles = getSampleStyleSheet()
    title = ParagraphStyle('cf-title', parent=styles['Title'], fontName=FONT_NAME, fontSize=24, leading=34, textColor=colors.HexColor('#1265bd'), alignment=TA_CENTER, spaceAfter=18)
    subtitle = ParagraphStyle('cf-subtitle', parent=styles['Normal'], fontName=FONT_NAME, fontSize=11, leading=18, alignment=TA_CENTER, textColor=colors.HexColor('#555555'))
    heading = ParagraphStyle('cf-heading', parent=styles['Heading2'], fontName=FONT_NAME, fontSize=15, leading=22, textColor=colors.HexColor('#1265bd'), spaceBefore=10, spaceAfter=8)
    body = ParagraphStyle('cf-body', parent=styles['BodyText'], fontName=FONT_NAME, fontSize=9.5, leading=17, alignment=TA_LEFT, spaceAfter=7)
    small = ParagraphStyle('cf-small', parent=body, fontSize=8.5, leading=14)
    story = [
        Spacer(1, 35 * mm), _paragraph('教学质量分析', heading),
        Spacer(1, 10 * mm), _paragraph(report.mission.mission_name, title),
        _paragraph('错题反馈话术表', title),
        Spacer(1, 8 * mm), _paragraph(f'班级：{report.class_obj.class_name}', subtitle),
        _paragraph(f'生成日期：{report.created_at:%Y-%m-%d}｜版本：{report.source_matrix_version}', subtitle),
        PageBreak(), _paragraph('目录', heading), Spacer(1, 8 * mm),
        _paragraph('一、班级整体掌握情况', body),
        _paragraph(f'二、学生个人反馈话术（{report.participant_count}人）', body),
        PageBreak(), _paragraph('一、班级整体掌握情况', heading),
    ]
    overview = [
        [_paragraph('参考人数', small), _paragraph('统计题量', small), _paragraph('累计错题', small), _paragraph('人均错题', small)],
        [_paragraph(f'{report.participant_count} 人', title), _paragraph(f'{report.question_count} 题', title), _paragraph(f'{report.total_wrong_count} 次', title), _paragraph(f'{report.average_wrong_count} 道', title)],
    ]
    overview_table = Table(overview, colWidths=[45 * mm] * 4)
    overview_table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.8, colors.HexColor('#444444')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'), ('TOPPADDING', (0, 0), (-1, -1), 8), ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    story += [overview_table, Spacer(1, 8 * mm), _paragraph(report.class_feedback_text, body)]
    story += [_paragraph('1.1 各知识板块错误情况', heading)]
    knowledge_rows = [[_paragraph(x, body) for x in ('知识板块', '错误次数', '错误率', '掌握情况')]]
    for row in report.knowledge_stats.all():
        mastery = {'good': '掌握较好', 'attention': '基本掌握，需巩固', 'weak': '薄弱，需重点训练'}.get(row.mastery_level, '待关注')
        knowledge_rows.append([_paragraph(row.knowledge_name, small), _paragraph(f'{row.wrong_count}', small), _paragraph(f'{row.error_rate}%', small), _paragraph(mastery, small)])
    story.append(_table(knowledge_rows, [45 * mm, 35 * mm, 35 * mm, 65 * mm]))
    story += [_paragraph('1.2 高错误率题目', heading)]
    question_rows = [[_paragraph(x, body) for x in ('题号', '考查知识点', '错误人数', '错误率')]]
    question_stats = list(report.question_stats.filter(wrong_count__gt=0).order_by('-wrong_rate', 'sort_no')[:20])
    for row in question_stats:
        question_rows.append([_paragraph(f'{row.node_name_snapshot or "未分节点"}·第{row.question_no}题', small), _paragraph('、'.join(row.knowledge_labels or []), small), _paragraph(f'{row.wrong_count} 人', small), _paragraph(f'{row.wrong_rate}%', small)])
    question_table = _table(question_rows, [30 * mm, 75 * mm, 35 * mm, 40 * mm])
    for index, row in enumerate(question_stats, 1):
        if float(row.wrong_rate) >= 50:
            question_table.setStyle(TableStyle([
                ('TEXTCOLOR', (3, index), (3, index), colors.red),
                ('FONTNAME', (3, index), (3, index), FONT_NAME),
            ]))
    story.append(question_table)
    story += [PageBreak(), _paragraph(f'二、学生个人反馈话术（{report.participant_count}人）', heading)]
    question_by_id = {str(item.source_question_id): item for item in report.question_stats.all()}
    for index, row in enumerate(report.student_feedbacks.all(), 1):
        knowledge_points = [item for item in (row.knowledge_summary or []) if item != '待归类题目']
        wrong_questions = [
            question_by_id[str(question_id)] for question_id in row.wrong_question_ids
            if str(question_id) in question_by_id
        ]
        wrong_question_text = '、'.join(
            f'{item.node_name_snapshot or "未分节点"}·第{item.question_no}题' for item in wrong_questions
        ) or '无'
        story.append(KeepTogether([
            _paragraph(f'{index}. {row.student_name_snapshot}', heading),
            _table([
                [_paragraph('项目', body), _paragraph('内容', body)],
                [_paragraph(f'错题（{row.wrong_count}道）', small), _paragraph(wrong_question_text, small)],
                [_paragraph('涉及板块', small), _paragraph('、'.join(row.knowledge_summary or []) or '待归类题目', small)],
                [_paragraph('核心错误知识点', small), _paragraph('、'.join(knowledge_points) or '待归类题目（请结合题干、解析和答案归纳）', small)],
                [_paragraph('重练安排', small), _paragraph('；'.join(row.review_arrangement or []) or '请结合错题完成订正和重练。', small)],
            ], [35 * mm, 145 * mm]),
        ]))
        story += [Spacer(1, 2 * mm), _paragraph(row.feedback_text, body)]
    try:
        document = SimpleDocTemplate(temporary, pagesize=A4, rightMargin=15 * mm, leftMargin=15 * mm, topMargin=15 * mm, bottomMargin=20 * mm, title='课堂错题反馈')
        document.build(story, onFirstPage=_footer, onLaterPages=_footer)
        os.replace(temporary, output)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return relative
