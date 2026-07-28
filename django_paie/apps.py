from django.apps import AppConfig


class DjangoPaieConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "django_paie"
    verbose_name = "Paie"

    def ready(self):
        from . import signals
