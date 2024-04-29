from hope_dedup_engine.config.settings import DEBUG, INSTALLED_APPS
from .middleware import MIDDLEWARE

if DEBUG:  # pragma: no cover
    INSTALLED_APPS += ("debug_toolbar",)  # noqa
    MIDDLEWARE += ("debug_toolbar.middleware.DebugToolbarMiddleware",)  # noqa
    DEBUG_TOOLBAR_CONFIG = {
        "SHOW_TEMPLATE_CONTEXT": True,
    }
