from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0005_useraccount_subjects'),
    ]

    operations = [
        migrations.AlterField(
            model_name='useraccount',
            name='mobile',
            field=models.CharField(blank=True, max_length=20, null=True, unique=True),
        ),
        migrations.AddField(
            model_name='useraccount',
            name='student_no',
            field=models.CharField(blank=True, db_index=True, default='', max_length=64),
        ),
    ]
