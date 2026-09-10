from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('institutions', '0005_classstudent_grade_and_class_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='studentimportrow',
            name='target_class',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='student_import_rows',
                to='institutions.class',
            ),
        ),
    ]
