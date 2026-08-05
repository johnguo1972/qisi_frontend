from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('parser', '0002_examquestion_barcode_data_examquestion_collected_at_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='questionimage',
            name='placement',
            field=models.CharField(
                choices=[('stem', '题干下方'), ('options', '选项下方')],
                default='stem',
                max_length=20,
                verbose_name='插图位置',
            ),
        ),
        migrations.AddField(
            model_name='questionimage',
            name='display_width',
            field=models.PositiveIntegerField(
                default=100,
                help_text='相对于渲染区宽度，范围 25-100',
                verbose_name='显示宽度百分比',
            ),
        ),
    ]
