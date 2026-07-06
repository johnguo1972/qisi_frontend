# Generated manually for paper_code and region fields
import re
from django.db import migrations, models


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


def generate_existing_paper_codes(apps, schema_editor):
    """Backfill paper_code for existing papers and seed counters."""
    from django.db import connection

    ExamPaper = apps.get_model('papers', 'ExamPaper')
    PaperCodeCounter = apps.get_model('papers', 'PaperCodeCounter')

    papers = list(ExamPaper.objects.filter(paper_code__isnull=True).order_by('created_at'))
    if not papers:
        return

    counters = {}  # (subject, grade_char) -> next_seq
    updates = []  # list of (id, paper_code)

    for paper in papers:
        subject = paper.subject or ''
        grade_char = _resolve_grade_char(paper.grade)
        key = (subject, grade_char)
        seq = counters.get(key, 1)
        counters[key] = seq + 1

        letter = SUBJECT_FIRST_LETTER.get(subject, 'X')
        code = f'{letter}{grade_char}{seq:04d}'
        updates.append((paper.id, code))

    # Use raw SQL to bypass model signals and unique constraint issues
    with connection.cursor() as cursor:
        for paper_id, code in updates:
            cursor.execute(
                'UPDATE tiku_exam_paper SET paper_code = %s WHERE id = %s',
                [code, paper_id],
            )

    # Seed counter rows (next_seq = max + 1)
    for (subject, grade_char), next_seq in counters.items():
        PaperCodeCounter.objects.update_or_create(
            subject=subject,
            grade_char=grade_char,
            defaults={'next_seq': next_seq},
        )


class Migration(migrations.Migration):

    dependencies = [
        ('papers', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='PaperCodeCounter',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('letter', models.CharField(max_length=1)),
                ('grade_char', models.CharField(max_length=1)),
                ('next_seq', models.IntegerField(default=1)),
            ],
            options={
                'verbose_name': '试卷编号计数器',
                'verbose_name_plural': '试卷编号计数器',
                'db_table': 'tiku_paper_code_counter',
                'unique_together': {('letter', 'grade_char')},
            },
        ),
        migrations.CreateModel(
            name='QuestionIDCounter',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('subject', models.CharField(max_length=50, unique=True)),
                ('next_seq', models.IntegerField(default=1)),
            ],
            options={
                'verbose_name': '题目系统编号计数器',
                'verbose_name_plural': '题目系统编号计数器',
                'db_table': 'tiku_question_id_counter',
            },
        ),
        migrations.AddField(
            model_name='exampaper',
            name='paper_code',
            field=models.CharField(
                max_length=20, unique=True, null=True, blank=True,
                verbose_name='试卷编号', db_index=True,
                help_text='如：M90001, PA0002',
            ),
        ),
        migrations.AddField(
            model_name='exampaper',
            name='region',
            field=models.CharField(
                max_length=100, null=True, blank=True,
                verbose_name='来源地区',
                help_text='如：全国卷, 广东卷, 深圳卷',
            ),
        ),
        migrations.RunPython(
            generate_existing_paper_codes,
            migrations.RunPython.noop,
        ),
    ]
