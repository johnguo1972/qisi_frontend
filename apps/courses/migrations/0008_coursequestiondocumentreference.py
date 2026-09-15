from django.db import migrations, models
import django.db.models.deletion
import uuid_utils.compat


class Migration(migrations.Migration):
    dependencies = [
        ('courses', '0007_coursequestionlink_source_document_question_no'),
        ('study', '0009_questiondocumentimporttask_tree_node'),
    ]

    operations = [
        migrations.CreateModel(
            name='CourseQuestionDocumentReference',
            fields=[
                ('id', models.UUIDField(default=uuid_utils.compat.uuid7, editable=False, primary_key=True, serialize=False)),
                ('source_fingerprint', models.CharField(db_index=True, max_length=64)),
                ('source_position', models.PositiveIntegerField()),
                ('source_question_no', models.CharField(blank=True, default='', max_length=100)),
                ('source_page_start', models.PositiveIntegerField(blank=True, null=True)),
                ('source_page_end', models.PositiveIntegerField(blank=True, null=True)),
                ('source_section_path', models.CharField(blank=True, default='', max_length=500)),
                ('source_locator', models.CharField(max_length=700)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('course_question_link', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='document_references', to='courses.coursequestionlink')),
                ('document_import_task', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='source_references', to='study.questiondocumentimporttask')),
            ],
            options={'db_table': 'course_question_document_reference'},
        ),
        migrations.AddConstraint(
            model_name='coursequestiondocumentreference',
            constraint=models.UniqueConstraint(fields=('document_import_task', 'source_position'), name='uq_course_doc_reference_task_position'),
        ),
    ]
