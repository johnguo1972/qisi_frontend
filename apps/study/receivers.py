"""学生端信号接收器：学生加入班级后回填任务进度。"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from apps.institutions.models import ClassStudent
from apps.missions.models import LearningMission
from .models import StudentMissionProgress


@receiver(post_save, sender=ClassStudent)
def backfill_mission_progress_on_join(sender, instance, created, **kwargs):
    """新增活跃班级成员时，为该班级所有已发布任务补建 StudentMissionProgress。"""
    if not created or instance.status != 'active':
        return
    missions = LearningMission.objects.filter(
        class_obj_id=instance.class_obj_id, status='published'
    )
    for mission in missions:
        StudentMissionProgress.objects.get_or_create(
            mission=mission,
            student_user_id_id=instance.student_id,
            defaults={'progress_status': 'not_started', 'progress_percent': 0},
        )
