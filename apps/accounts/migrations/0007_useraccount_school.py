from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0006_student_identifier'),
    ]

    operations = [
        migrations.AddField(
            model_name='useraccount',
            name='school',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
    ]
