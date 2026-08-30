from django.db import migrations


class Migration(migrations.Migration):
    """Join the remote material-status branch and local course-relations branch."""

    dependencies = [
        ('courses', '0004_coursematerial_conversion_status'),
        ('courses', '0005_coursehandout_handout_courseclass_uq_course_class_and_more'),
    ]

    operations = []
