from django.db import migrations, models


def copy_legacy_subjects(apps, schema_editor):
    UserAccount = apps.get_model('accounts', 'UserAccount')
    for user in UserAccount.objects.exclude(subject__isnull=True).exclude(subject='').iterator():
        user.subjects = [user.subject]
        user.save(update_fields=['subjects'])


def clear_subject_lists(apps, schema_editor):
    UserAccount = apps.get_model('accounts', 'UserAccount')
    UserAccount.objects.update(subjects=None)


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0004_wechatwebidentity'),
    ]

    operations = [
        migrations.AddField(
            model_name='useraccount',
            name='subjects',
            field=models.JSONField(blank=True, null=True),
        ),
        migrations.RunPython(copy_legacy_subjects, clear_subject_lists),
    ]
