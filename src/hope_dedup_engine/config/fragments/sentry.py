from hope_dedup_engine.config import env

SENTRY_DSN = env("SENTRY_DSN", default=None)  # noqa: F405

if SENTRY_DSN:  # pragma: no cover
    import sentry_sdk
    from sentry_sdk.integrations.celery import CeleryIntegration
    from sentry_sdk.integrations.django import DjangoIntegration

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        # by default this is False, must be set to True so the library attaches the request data to the event
        send_default_pii=True,
        integrations=[DjangoIntegration(), CeleryIntegration()],
        environment=env("SENTRY_ENVIRONMENT", default=None),
    )
