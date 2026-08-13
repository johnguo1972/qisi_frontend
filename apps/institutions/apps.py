from django.apps import AppConfig


class InstitutionsConfig(AppConfig):
    def ready(self):
        from . import signals  # noqa: F401

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.institutions'
    label = 'institutions'
