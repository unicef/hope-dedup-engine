from django.apps import AppConfig


class ApiConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "hope_dedup_engine.apps.api"

    def ready(self) -> None:
        import hope_dedup_engine.apps.api.signals  # noqa: F401
