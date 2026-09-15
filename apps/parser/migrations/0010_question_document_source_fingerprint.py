import uuid_utils.compat
from django.db import migrations, models
import django.db.models.deletion
import apps.parser.question_identity


class Migration(migrations.Migration):
    dependencies = [('parser', '0009_question_content_fingerprint')]
    operations = [
        migrations.CreateModel(
            name='QuestionDocumentSourceFingerprint',
            fields=[
                ('id', models.UUIDField(default=uuid_utils.compat.uuid7, editable=False, primary_key=True, serialize=False)),
                ('fingerprint', models.CharField(max_length=64, unique=True, validators=[apps.parser.question_identity.validate_content_fingerprint])),
                ('algorithm_version', models.CharField(default='document-source-v1', max_length=32)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('canonical_question', models.ForeignKey(db_column='canonical_question_id', on_delete=django.db.models.deletion.CASCADE, related_name='document_source_fingerprints', to='parser.examquestion')),
            ],
            options={'db_table': 'tiku_question_document_source_fingerprint'},
        ),
    ]
