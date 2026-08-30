from django.db import migrations
import re


def _question_no_key(value):
    text = str(value or '').strip()
    tokens = re.findall(r'\d+|[^\d]+', text)
    return tuple(
        (0, int(token)) if token.isdigit() else (1, token.strip().lower())
        for token in tokens
    ) or ((1, ''),)


def normalize_order(apps, schema_editor):
    MissionQuestionRel = apps.get_model('missions', 'MissionQuestionRel')
    ExamQuestion = apps.get_model('parser', 'ExamQuestion')
    for mission_id in MissionQuestionRel.objects.values_list('mission_id', flat=True).distinct():
        relations = list(MissionQuestionRel.objects.filter(mission_id=mission_id).order_by('sort_no', 'id'))
        question_numbers = {
            str(row['id']): row['question_no']
            for row in ExamQuestion.objects.filter(
                id__in=[relation.question_id for relation in relations]
            ).values('id', 'question_no')
        }
        relations.sort(key=lambda relation: (
            _question_no_key(question_numbers.get(str(relation.question_id), '')),
            relation.sort_no,
            str(relation.id),
        ))
        changed = []
        for sort_no, relation in enumerate(relations, start=1):
            if relation.sort_no != sort_no:
                relation.sort_no = sort_no
                changed.append(relation)
        if changed:
            MissionQuestionRel.objects.bulk_update(changed, ['sort_no'])


class Migration(migrations.Migration):
    dependencies = [
        ('missions', '0013_wrongbookgenerationitem_error_stage'),
    ]

    operations = [
        migrations.RunPython(normalize_order, migrations.RunPython.noop),
    ]
