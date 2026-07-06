# Data migration to backfill paper_code for existing papers
import re
from django.db import migrations


SUBJECT_FIRST_LETTER = {
    '数学': 'M',
    '物理': 'P',
    '化学': 'H',
    '生物': 'S',
    '语文': 'Y',
    '英语': 'E',
}

GRADE_CHAR_MAP = {
    '1': '1', '2': '2', '3': '3', '4': '4', '5': '5',
    '6': '6', '7': '7', '8': '8', '9': '9',
    '一年级': '1', '二年级': '2', '三年级': '3',
    '四年级': '4', '五年级': '5', '六年级': '6',
    '七年级': '7', '八年级': '8', '九年级': '9',
    '高一': 'A', '高二': 'B', '高三': 'C',
    '10': 'A', '11': 'B', '12': 'C',
}


def _resolve_grade_char(grade):
    if not grade:
        return 'X'
    grade = grade.strip()
    if grade in GRADE_CHAR_MAP:
        return GRADE_CHAR_MAP[grade]
    match = re.search(r'(\d+)', grade)
    if match:
        num = int(match.group(1))
        if 1 <= num <= 9:
            return str(num)
        elif num == 10:
            return 'A'
        elif num == 11:
            return 'B'
        elif num == 12:
            return 'C'
    return 'X'


def backfill_paper_codes(apps, schema_editor):
    """Backfill paper_code for existing papers and seed counters."""
    from django.db import connection

    ExamPaper = apps.get_model('papers', 'ExamPaper')
    PaperCodeCounter = apps.get_model('papers', 'PaperCodeCounter')

    papers = list(ExamPaper.objects.filter(paper_code__isnull=True).order_by('created_at'))
    if not papers:
        return

    counters = {}  # (letter, grade_char) -> next_seq  <-- use letter, not subject
    updates = []

    for paper in papers:
        subject = paper.subject or ''
        grade_char = _resolve_grade_char(paper.grade)
        letter = SUBJECT_FIRST_LETTER.get(subject, 'X')
        key = (letter, grade_char)
        seq = counters.get(key, 1)
        counters[key] = seq + 1

        code = f'{letter}{grade_char}{seq:04d}'
        updates.append((paper.id, code))

    with connection.cursor() as cursor:
        for paper_id, code in updates:
            cursor.execute(
                'UPDATE tiku_exam_paper SET paper_code = %s WHERE id = %s',
                [code, paper_id],
            )

    # Seed counter rows using (letter, grade_char) keys
    for (letter, grade_char), next_seq in counters.items():
        PaperCodeCounter.objects.update_or_create(
            letter=letter,
            grade_char=grade_char,
            defaults={'next_seq': next_seq},
        )


def reverse_backfill(apps, schema_editor):
    ExamPaper = apps.get_model('papers', 'ExamPaper')
    ExamPaper.objects.update(paper_code=None)


class Migration(migrations.Migration):

    dependencies = [
        ('papers', '0002_add_paper_fields'),
    ]

    operations = [
        migrations.RunPython(
            backfill_paper_codes,
            reverse_backfill,
        ),
    ]
