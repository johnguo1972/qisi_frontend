from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('missions', '0006_learningmission_assignment_mode'),
    ]

    operations = [
        migrations.AddField(
            model_name='learningmission',
            name='pdf_file_path',
            field=models.CharField(blank=True, default='', max_length=500),
        ),
    ]
