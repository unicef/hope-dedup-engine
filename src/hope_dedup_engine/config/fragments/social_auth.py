from hope_dedup_engine.config import env

SOCIAL_AUTH_SECRET = env.str("AZURE_CLIENT_SECRET", default="")
SOCIAL_AUTH_TENANT_ID = env("AZURE_TENANT_ID", default="")
SOCIAL_AUTH_KEY = env.str("AZURE_CLIENT_KEY", default="")

SOCIAL_AUTH_URL_NAMESPACE = "social"
SOCIAL_AUTH_SANITIZE_REDIRECTS = False
SOCIAL_AUTH_JSONFIELD_ENABLED = True
SOCIAL_AUTH_USER_MODEL = "core.User"

SOCIAL_AUTH_PIPELINE = (
    "unicef_security.pipeline.social_details",
    "social_core.pipeline.social_auth.social_uid",
    "social_core.pipeline.social_auth.auth_allowed",
    "social_core.pipeline.social_auth.social_user",
    "social_core.pipeline.user.get_username",
    "social_core.pipeline.social_auth.associate_by_email",
    "unicef_security.pipeline.create_unicef_user",
    "social_core.pipeline.social_auth.associate_user",
    "social_core.pipeline.social_auth.load_extra_data",
    "social_core.pipeline.user.user_details",
)
