from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('courses', '0006_merge_remote_material_status_and_local_course_relations')]

    operations = [
        migrations.AddField(
            model_name='coursequestionlink',
            name='source_document_question_no',
            field=models.CharField(blank=True, db_index=True, max_length=100, null=True),
        ),
    ]
