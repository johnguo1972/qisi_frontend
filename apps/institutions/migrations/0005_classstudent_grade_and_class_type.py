import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0008_studentparentbind_primary'),
        ('institutions', '0004_class_grade_level'),
    ]

    operations = [
        migrations.AddField(
            model_name='classstudent',
            name='grade_level',
            field=models.CharField(blank=True, max_length=20, null=True),
        ),
        migrations.AddField(
            model_name='classstudent',
            name='class_type',
            field=models.CharField(blank=True, max_length=20, null=True),
        ),
    ]
