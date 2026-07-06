# Generated manually for question numbering fields
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

CHINESE_NUMERAL_TO_INT = [
    ('十二', 12), ('十一', 11), ('十', 10),
    ('九', 9), ('八', 8), ('七', 7), ('六', 6),
    ('五', 5), ('四', 4), ('三', 3), ('二', 2), ('一', 1),
]


def extract_major_section_no(section_title):
    if not section_title:
        return 0
    for numeral, value in CHINESE_NUMERAL_TO_INT:
        if section_title.startswith(numeral):
            return value
    match = re.match(r'^(\d+)', section_title)
    if match:
        return int(match.group(1))
    return 0


def generate_existing_question_ids(apps, schema_editor):
    """Backfill system_id and paper_question_no for existing questions."""
    from django.db import connection

    ExamQuestion = apps.get_model('parser', 'ExamQuestion')
    ExamPaper = apps.get_model('papers', 'ExamPaper')
    QuestionIDCounter = apps.get_model('papers', 'QuestionIDCounter')

    # --- Step 1: Generate system_id per subject ---
    questions = list(ExamQuestion.objects.filter(system_id__isnull=True).order_by('subject', 'created_at'))
    if questions:
        counters = {}  # subject -> next_seq
        updates = []
        for q in questions:
            subject = q.subject or ''
            seq = counters.get(subject, 1)
            counters[subject] = seq + 1
            letter = SUBJECT_FIRST_LETTER.get(subject, 'X')
            updates.append((q.id, f'{letter}{seq:05X}'))

        # Use raw SQL to avoid unique constraint conflicts during migration
        with connection.cursor() as cursor:
            for qid, sys_id in updates:
                cursor.execute(
                    'UPDATE tiku_exam_question SET system_id = %s WHERE id = %s',
                    [sys_id, qid],
                )

        # Seed counter rows
        for subject, next_seq in counters.items():
            QuestionIDCounter.objects.update_or_create(
                subject=subject,
                defaults={'next_seq': next_seq},
            )

    # --- Step 2: Generate paper_question_no ---
    paper_ids = list(ExamQuestion.objects.filter(
        paper_question_no__isnull=True
    ).values_list('paper_id', flat=True).distinct())

    for paper_id in paper_ids:
        paper = ExamPaper.objects.filter(id=paper_id).first()
        if not paper:
            continue
        paper_code = paper.paper_code or f'P{paper_id}'

        qs = list(
            ExamQuestion.objects
            .filter(paper_id=paper_id, paper_question_no__isnull=True)
            .order_by('section_title', 'sort_order')
        )

        section_counters = {}
        updates = []
        for q in qs:
            section_title = q.section_title or ''
            major_no = extract_major_section_no(section_title)

            if section_title not in section_counters:
                section_counters[section_title] = 1
            minor_no = section_counters[section_title]
            section_counters[section_title] += 1

            updates.append((q.id, f'{paper_code}-{major_no}-{minor_no}'))

        with connection.cursor() as cursor:
            for qid, pqn in updates:
                cursor.execute(
                    'UPDATE tiku_exam_question SET paper_question_no = %s WHERE id = %s',
                    [pqn, qid],
                )


class Migration(migrations.Migration):

    dependencies = [
        ('parser', '0002_alter_aiparseresult_table_alter_exampage_table_and_more'),
        ('papers', '0002_add_paper_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='examquestion',
            name='system_id',
            field=models.CharField(
                max_length=10, unique=True, null=True, blank=True,
                verbose_name='系统编号', db_index=True,
                help_text='如：M00001',
            ),
        ),
        migrations.AddField(
            model_name='examquestion',
            name='paper_question_no',
            field=models.CharField(
                max_length=50, null=True, blank=True,
                verbose_name='试卷题号', db_index=True,
                help_text='如：M90001-1-3',
            ),
        ),
        migrations.AddIndex(
            model_name='examquestion',
            index=models.Index(fields=['system_id'], name='idx_system_id'),
        ),
        migrations.AddIndex(
            model_name='examquestion',
            index=models.Index(fields=['paper_question_no'], name='idx_paper_qno'),
        ),
        migrations.RunPython(
            generate_existing_question_ids,
            migrations.RunPython.noop,
        ),
    ]
