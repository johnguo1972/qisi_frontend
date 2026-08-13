from django.apps import AppConfig


class AccountsConfig(AppConfig):
    def ready(self):
        from . import signals  # noqa: F401

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.accounts'
    verbose_name = '用户管理'
