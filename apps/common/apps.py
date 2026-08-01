"""Django application configuration for shared services."""

from django.apps import AppConfig


class CommonConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.common"

    def ready(self) -> None:
        from .ai.config import load_ai_config

        load_ai_config()
