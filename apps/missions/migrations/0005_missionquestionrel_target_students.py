from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('missions', '0004_learningmission_course')]
    operations = [migrations.AddField(
        model_name='missionquestionrel', name='target_student_ids',
        field=models.JSONField(blank=True, default=list),
    )]
