from django.db import migrations, models
from django.db.models import Q


def mark_existing_primary_bindings(apps, schema_editor):
    StudentParentBind = apps.get_model('accounts', 'StudentParentBind')

    active_rows = StudentParentBind.objects.filter(
        bind_status='active',
    ).order_by('student_user_id', 'bound_at', 'id')
    seen_students = set()
    for relation in active_rows.iterator():
        if relation.student_user_id in seen_students:
            continue
        relation.is_primary = True
        relation.save(update_fields=['is_primary'])
        seen_students.add(relation.student_user_id)


def unmark_primary_bindings(apps, schema_editor):
    StudentParentBind = apps.get_model('accounts', 'StudentParentBind')
    StudentParentBind.objects.update(is_primary=False)


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0007_useraccount_school'),
    ]

    operations = [
        migrations.AddField(
            model_name='studentparentbind',
            name='is_primary',
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(
            mark_existing_primary_bindings,
            unmark_primary_bindings,
        ),
        migrations.AddConstraint(
            model_name='studentparentbind',
            constraint=models.UniqueConstraint(
                condition=Q(bind_status='active', is_primary=True),
                fields=('student_user_id',),
                name='uq_active_primary_parent_per_student',
            ),
        ),
    ]
