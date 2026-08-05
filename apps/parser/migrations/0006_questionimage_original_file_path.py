from django.db import migrations, models
from django.db.models import F


def preserve_current_images_as_originals(apps, schema_editor):
    QuestionImage = apps.get_model('parser', 'QuestionImage')
    QuestionImage.objects.filter(original_file_path__isnull=True).update(
        original_file_path=F('file_path')
    )


class Migration(migrations.Migration):
    dependencies = [
        ('parser', '0005_alter_questionimage_display_width'),
    ]

    operations = [
        migrations.AddField(
            model_name='questionimage',
            name='original_file_path',
            field=models.CharField(blank=True, help_text='用于在多次裁切、旋转或翻转后恢复未经编辑的原图', max_length=500, null=True, verbose_name='原始图片路径'),
        ),
        migrations.RunPython(preserve_current_images_as_originals, migrations.RunPython.noop),
    ]
