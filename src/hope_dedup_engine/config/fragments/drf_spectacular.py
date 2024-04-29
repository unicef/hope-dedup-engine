from hope_dedup_engine.config.settings import DEBUG, INSTALLED_APPS
from .drf import REST_FRAMEWORK

if DEBUG:  # pragma: no cover
    INSTALLED_APPS += ("drf_spectacular", "drf_spectacular_sidecar")  # noqa        
    REST_FRAMEWORK["DEFAULT_SCHEMA_CLASS"] = "drf_spectacular.openapi.AutoSchema"
    SPECTACULAR_SETTINGS = {
        "TITLE": "Payment Gateway API",
        "DESCRIPTION": "Payment Gateway to integrate HOPE with FSP",
        "VERSION": "1.0.0",
        "SERVE_INCLUDE_SCHEMA": True,
        "SWAGGER_UI_DIST": "SIDECAR",
        "SWAGGER_UI_FAVICON_HREF": "SIDECAR",
        "REDOC_DIST": "SIDECAR",
    }
