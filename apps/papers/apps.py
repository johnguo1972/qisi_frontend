from django.apps import AppConfig


class PapersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.papers'
    verbose_name = '试卷管理'

    def ready(self):
        import apps.papers.signals  # noqa
