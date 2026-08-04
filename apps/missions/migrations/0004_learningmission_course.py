from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('missions', '0003_learningmission_target_student_ids'), ('courses', '0001_initial')]
    operations = [migrations.AddField(
        model_name='learningmission', name='course',
        field=models.ForeignKey(blank=True, db_column='course_id', null=True,
                                on_delete=django.db.models.deletion.SET_NULL,
                                related_name='learning_missions', to='courses.course'),
    )]
