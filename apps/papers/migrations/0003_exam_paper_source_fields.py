from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('papers', '0002_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='exampaper',
            name='source_package_id',
            field=models.CharField(blank=True, db_index=True, max_length=255, null=True, unique=True, verbose_name='来源数据包标识'),
        ),
        migrations.AddField(
            model_name='exampaper',
            name='source_sha256',
            field=models.CharField(blank=True, db_index=True, max_length=64, null=True, verbose_name='来源文件SHA256'),
        ),
    ]
