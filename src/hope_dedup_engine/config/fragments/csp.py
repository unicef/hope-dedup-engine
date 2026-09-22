# Content-Security-Policy (django-csp).
#
# django-csp >= 4.0 uses the CONTENT_SECURITY_POLICY dict format.
# The legacy CSP_* top-level settings are no longer honored and only emit
# a warning via the csp.E001 system check.
#
# `'unsafe-inline'` / `'unsafe-eval'` are still required by the bundled
# admin/editor/charting assets. Migrating away from them (nonces / hashes,
# strict CSP) must be done incrementally; start with CONTENT_SECURITY_POLICY
# in "report-only" mode and monitor before enforcing a stricter policy, see
# https://cheatsheetseries.owasp.org/cheatsheets/Content_Security_Policy_Cheat_Sheet.html

CONTENT_SECURITY_POLICY = {
    "DIRECTIVES": {
        "default-src": ["'self'", "'unsafe-inline'"],
        "style-src": [
            "'self'",
            "'unsafe-inline'",
            "same-origin",
            "fonts.googleapis.com",
            "fonts.gstatic.com",
        ],
        "script-src": ["'self'", "'unsafe-inline'", "same-origin", "blob:"],
        "img-src": [
            "'self'",
            "'unsafe-inline'",
            "same-origin",
            "blob:",
            "data:",
            "cdn.redoc.ly",
        ],
        "font-src": [
            "'self'",
            "fonts.googleapis.com",
            "same-origin",
            "fonts.googleapis.com",
            "fonts.gstatic.com",
            "blob:",
        ],
        "frame-src": ["'self'"],
        "object-src": ["'none'"],
        "base-uri": ["'self'"],
    },
}
