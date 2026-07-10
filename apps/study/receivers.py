"""学生端信号接收器：学生加入班级后回填任务进度 + AI 答案自动生成。"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from apps.institutions.models import ClassStudent
from apps.missions.models import LearningMission
from apps.parser.models import ExamQuestion
from .models import StudentMissionProgress
from apps.common.batch_tasks import single_generate_ai_answers


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


@receiver(post_save, sender=ExamQuestion)
def auto_trigger_ai_generation(sender, instance, created, **kwargs):
    """当题目解析完成（parse_status='auto_parsed'）且未生成过 AI 答案时，自动触发。

    ⚠️ 注意：post_save 在每次 save() 都会触发，但条件 `not instance.ai_answer_a`
    确保 save_results_to_question 写入后不会再次触发，无递归风险。
    """
    if instance.parse_status == 'auto_parsed' and not instance.ai_answer_a:
        single_generate_ai_answers.delay(instance.id)
