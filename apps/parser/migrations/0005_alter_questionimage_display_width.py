from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('parser', '0004_alter_questionimage_display_width'),
    ]

    operations = [
        migrations.AlterField(
            model_name='questionimage',
            name='display_width',
            field=models.PositiveIntegerField(
                default=100,
                help_text='图片显示宽度（像素），范围 80-1200，前端通过画布滚轮调整',
                verbose_name='图片显示宽度',
            ),
        ),
    ]
