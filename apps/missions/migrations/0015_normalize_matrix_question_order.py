from django.db import migrations


def _question_no_key(value):
    import re

    text = str(value or '').strip()
    tokens = re.findall(r'\d+|[^\d]+', text)
    if not tokens:
        return ((1, ''),)
    return tuple(
        (0, int(token)) if token.isdigit() else (1, token.strip().lower())
        for token in tokens
    )


def normalize_matrix_question_order(apps, schema_editor):
    Matrix = apps.get_model('missions', 'TeacherWrongBookMatrix')
    MatrixQuestion = apps.get_model('missions', 'TeacherWrongBookMatrixQuestion')
    matrix_ids = MatrixQuestion.objects.values_list('matrix_id', flat=True).distinct()
    for matrix_id in matrix_ids:
        rows = list(MatrixQuestion.objects.filter(
            matrix_id=matrix_id, status='active',
        ).order_by('sort_no', 'id'))
        rows.sort(key=lambda row: (
            _question_no_key(row.question_no_snapshot), row.sort_no, str(row.id),
        ))
        for sort_no, row in enumerate(rows, start=1):
            if row.sort_no != sort_no:
                row.sort_no = sort_no
                row.save(update_fields=['sort_no'])


class Migration(migrations.Migration):
    dependencies = [
        ('missions', '0014_normalize_mission_question_order'),
    ]

    operations = [
        migrations.RunPython(normalize_matrix_question_order, migrations.RunPython.noop),
    ]
