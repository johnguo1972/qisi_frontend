"""Auto-generate paper_code when a new ExamPaper is created."""
from django.db.models.signals import pre_save
from django.dispatch import receiver
from .models import ExamPaper
from apps.common.codegen import generate_paper_code


@receiver(pre_save, sender=ExamPaper)
def auto_generate_paper_code(sender, instance, **kwargs):
    """Generate paper_code on first save if not already set."""
    if not instance.pk and not instance.paper_code:
        instance.paper_code = generate_paper_code(instance.subject, instance.grade)
