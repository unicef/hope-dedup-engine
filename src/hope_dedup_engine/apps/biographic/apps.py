from django.apps import AppConfig


class Config(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "hope_dedup_engine.apps.biographic"
    verbose_name = "Biographic"
