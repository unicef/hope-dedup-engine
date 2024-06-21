from django.apps import AppConfig


class Config(AppConfig):
    name = __name__.rpartition(".")[0]
    verbose_name = "Core"

    def ready(self) -> None:
        super().ready()
        from hope_dedup_engine.utils import flags  # noqa
        from . import checks  # noqa
