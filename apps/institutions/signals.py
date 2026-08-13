from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.accounts.roles import grant_user_role
from apps.institutions.models import ClassStudent


@receiver(post_save, sender=ClassStudent)
def grant_student_role_for_active_membership(sender, instance, **kwargs):
    if instance.status == "active":
        grant_user_role(instance.student, "student")
