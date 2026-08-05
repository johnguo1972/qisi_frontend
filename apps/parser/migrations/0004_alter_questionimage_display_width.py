from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('parser', '0003_questionimage_layout'),
    ]

    operations = [
        migrations.AlterField(
            model_name='questionimage',
            name='display_width',
            field=models.PositiveIntegerField(
                default=100,
                help_text='图片显示缩放值，范围 25-200，前端通过画布滚轮调整',
                verbose_name='显示缩放值',
            ),
        ),
    ]
