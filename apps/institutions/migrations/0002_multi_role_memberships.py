from django.db import migrations, models
from django.db.models import Case, Count, IntegerField, Value, When


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


def collapse_memberships_and_preserve_role_grants(apps, schema_editor):
    """Fold multi-role memberships before the legacy unique key is restored.

    A global teacher or student grant may also come from another institution,
    class, or later business workflow. This migration stores no per-relationship
    provenance, so deleting a grant during reversal could remove a still-valid
    role. Schema reversal restores the old membership constraint; imported
    global grants deliberately remain active.

    The legacy schema can retain only one row per institution and user. Prefer
    an active membership, then admin over teacher, then the earliest row. The
    retained row keeps its own status and profile data; other rows are removed.
    """
    InstitutionMember = apps.get_model('institutions', 'InstitutionMember')
    duplicate_pairs = InstitutionMember.objects.values(
        'institution_id', 'user_id',
    ).annotate(row_count=Count('id')).filter(row_count__gt=1)

    status_order = Case(
        When(status='active', then=Value(0)),
        default=Value(1),
        output_field=IntegerField(),
    )
    role_order = Case(
        When(role='admin', then=Value(0)),
        When(role='teacher', then=Value(1)),
        default=Value(2),
        output_field=IntegerField(),
    )
    for pair in duplicate_pairs.iterator():
        rows = InstitutionMember.objects.filter(
            institution_id=pair['institution_id'],
            user_id=pair['user_id'],
        ).order_by(status_order, role_order, 'joined_at', 'pk')
        retained = rows.first()
        rows.exclude(pk=retained.pk).delete()


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
        migrations.RunPython(
            import_relationship_roles,
            collapse_memberships_and_preserve_role_grants,
        ),
    ]
