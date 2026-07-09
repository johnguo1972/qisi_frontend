from django.apps import AppConfig


class StudyConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.study'
    verbose_name = '学习作答'

    def ready(self):
        # 注册学生端信号接收器（导入即注册）
        from . import receivers  # noqa: F401
