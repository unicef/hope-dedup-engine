# Content-Security-Policy (django-csp).
#
# django-csp >= 4.0 uses the CONTENT_SECURITY_POLICY dict format.
# The legacy CSP_* top-level settings are no longer honored and only emit
# a warning via the csp.E001 system check.
#
# `'unsafe-inline'` is still required by the bundled admin/editor/charting
# assets. Extra origins that serve those files (Azure Blob, local Azurite)
# come from CSP_ASSET_HOSTS. CSP matches the origin, not the file path.

from hope_dedup_engine.config import env

ASSET_HOSTS = [host.strip() for host in env("CSP_ASSET_HOSTS") if host.strip()]

CONTENT_SECURITY_POLICY = {
    "DIRECTIVES": {
        "default-src": ["'self'", "'unsafe-inline'"],
        "style-src": [
            "'self'",
            "'unsafe-inline'",
            *ASSET_HOSTS,
            "fonts.googleapis.com",
            "fonts.gstatic.com",
        ],
        "script-src": ["'self'", "'unsafe-inline'", *ASSET_HOSTS, "blob:"],
        "img-src": [
            "'self'",
            "'unsafe-inline'",
            *ASSET_HOSTS,
            "blob:",
            "data:",
            "cdn.redoc.ly",
        ],
        "font-src": [
            "'self'",
            *ASSET_HOSTS,
            "fonts.googleapis.com",
            "fonts.gstatic.com",
            "blob:",
        ],
        "frame-src": ["'self'"],
        "object-src": ["'none'"],
        "base-uri": ["'self'"],
    },
}
