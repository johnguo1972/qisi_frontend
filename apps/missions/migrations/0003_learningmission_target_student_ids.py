from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('missions', '0002_alter_missionquestionrel_question_id')]
    operations = [migrations.AddField(
        model_name='learningmission', name='target_student_ids',
        field=models.JSONField(blank=True, default=list),
    )]
