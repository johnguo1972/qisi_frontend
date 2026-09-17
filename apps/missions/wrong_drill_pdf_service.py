"""PDF output for classroom wrong-drill packages."""
from pathlib import Path
from xml.sax.saxutils import escape

import fitz
from django.conf import settings


def generate_wrong_drill_pdf(package, questions):
    from apps.study.student_views import _build_pdf

    cover_pdf = _build_cover_pdf(package)
    exercise_pdf = _build_pdf('wrongbook', questions, False)
    answer_pdf = _build_pdf('wrongbook', questions, True, answer_only=True)
    merged = fitz.open()
    with fitz.open(stream=cover_pdf, filetype='pdf') as document:
        merged.insert_pdf(document)
    with fitz.open(stream=exercise_pdf, filetype='pdf') as document:
        merged.insert_pdf(document)
    with fitz.open(stream=answer_pdf, filetype='pdf') as document:
        merged.insert_pdf(document)
    relative = Path('exports') / 'wrong_drill' / str(package.id) / package.file_name
    destination = Path(settings.MEDIA_ROOT) / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(merged.tobytes())
    merged.close()
    return relative.as_posix()


def _build_cover_pdf(package):
    """Build the fixed first page required by the classroom drill template."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
    import io
    from django.utils import timezone

    pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light'))
    matrix = package.batch.matrix
    source = package.batch.source_set
    from .classroom_wrong_drill_service import _lecture_label
    items = list(package.items.select_related('source_question').order_by('sort_no'))
    wrong_numbers = '、'.join(item.wrong_question_no for item in items) or '无'
    knowledge = []
    for item in items:
        snapshot = item.content_snapshot or (item.source_question.question_snapshot if item.source_question else {})
        for point in snapshot.get('knowledge_points', []) or []:
            value = point.get('module') if isinstance(point, dict) else point
            if value and value not in knowledge:
                knowledge.append(str(value))
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=18 * mm, bottomMargin=18 * mm, leftMargin=18 * mm, rightMargin=18 * mm)
    styles = getSampleStyleSheet()
    title = ParagraphStyle('WrongDrillCoverTitle', parent=styles['Title'], fontName='STSong-Light', fontSize=17, leading=24, alignment=1, textColor=colors.HexColor('#1f4e79'))
    heading = ParagraphStyle('WrongDrillCoverHeading', parent=styles['Heading2'], fontName='STSong-Light', fontSize=11, leading=17, textColor=colors.HexColor('#1f4e79'))
    body = ParagraphStyle('WrongDrillCoverBody', parent=styles['Normal'], fontName='STSong-Light', fontSize=10, leading=17)
    story = [
        Paragraph('错题重练（个性化定制）', title), Spacer(1, 8 * mm),
        Paragraph(f'{escape(_lecture_label(source.source_node_name))}《{escape(source.workbook_title or matrix.source_mission.mission_name)}》错题重练', heading),
        Spacer(1, 5 * mm),
        Paragraph(f'姓名：{escape(package.student.display_name or package.student.mobile)}　　班级：{escape(getattr(matrix.class_obj, "class_name", ""))}', body),
        Paragraph(f'日期：{timezone.now().strftime("%Y 年 %m 月 %d 日")}', body), Spacer(1, 6 * mm),
        Paragraph('【本次错题统计】', heading),
        Paragraph(f'本次课堂错题共 {len(set(wrong_numbers.split("、")))} 题：{escape(wrong_numbers)}。本页正文仅呈现对应的错题练习题。', body),
        Spacer(1, 4 * mm), Paragraph('【精练题统计】', heading),
        Paragraph(f'已匹配并生成精练题 {len(items)} 题。精练题来源：错题练习题导入源。', body),
        Spacer(1, 4 * mm), Paragraph('【错误知识点归纳】', heading),
        Paragraph(escape('、'.join(knowledge) if knowledge else '以本次精练题为准，完成后结合解析复盘。'), body),
        Spacer(1, 6 * mm), Paragraph('【使用建议】', heading),
        Paragraph('1．先独立完成本次错题重练；<br/>2．完成后重点复盘错误知识点；<br/>3．对重点错题进行订正，确保每一步都理解；<br/>4．仍有疑问的题目及时向老师提问。', body),
    ]
    doc.build(story)
    return buffer.getvalue()
