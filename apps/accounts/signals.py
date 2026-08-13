from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.accounts.models import StudentParentBind
from apps.accounts.roles import grant_user_role


@receiver(post_save, sender=StudentParentBind)
def grant_roles_for_active_parent_bind(sender, instance, **kwargs):
    if instance.bind_status == "active":
        grant_user_role(instance.student_user_id, "student")
        grant_user_role(instance.parent_user_id, "parent")
