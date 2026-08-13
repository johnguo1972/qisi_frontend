from django.db import migrations, models


def import_relationship_roles(apps, schema_editor):
    InstitutionMember = apps.get_model('institutions', 'InstitutionMember')
    ClassStudent = apps.get_model('institutions', 'ClassStudent')
    UserRole = apps.get_model('accounts', 'UserRole')

    teacher_ids = InstitutionMember.objects.filter(
        role='teacher', status='active',
    ).values_list('user_id', flat=True).distinct()
    student_ids = ClassStudent.objects.filter(
        status='active',
    ).values_list('student_id', flat=True).distinct()

    for user_id in teacher_ids.iterator():
        UserRole.objects.update_or_create(
            user_id=user_id,
            role='teacher',
            defaults={'status': 'active'},
        )
    for user_id in student_ids.iterator():
        UserRole.objects.update_or_create(
            user_id=user_id,
            role='student',
            defaults={'status': 'active'},
        )


class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0003_userrole'),
        ('institutions', '0001_initial'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='institutionmember',
            unique_together=set(),
        ),
        migrations.AddConstraint(
            model_name='institutionmember',
            constraint=models.UniqueConstraint(
                fields=('institution', 'user', 'role'),
                name='uq_institution_member_role',
            ),
        ),
        migrations.RunPython(import_relationship_roles, migrations.RunPython.noop),
    ]
