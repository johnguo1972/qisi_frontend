from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('institutions', '0003_student_import'),
    ]

    operations = [
        migrations.AddField(
            model_name='class',
            name='grade_level',
            field=models.CharField(blank=True, max_length=20, null=True),
        ),
    ]
