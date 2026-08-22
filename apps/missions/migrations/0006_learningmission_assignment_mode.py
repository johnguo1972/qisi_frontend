from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('missions', '0005_missionquestionrel_target_students'),
    ]

    operations = [
        migrations.AddField(
            model_name='learningmission',
            name='assignment_mode',
            field=models.CharField(default='levels', max_length=20),
        ),
    ]
