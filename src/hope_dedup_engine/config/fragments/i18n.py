from hope_dedup_engine.config import env
from .templates import TEMPLATES

TIME_ZONE = env('TIME_ZONE', default='UTC')

# Language code for this installation. All choices can be found here:
# http://www.i18nguy.com/unicode/language-identifiers.html
LANGUAGE_CODE = "en-us"
ugettext = lambda s: s  # noqa
LANGUAGES = (
    ("es", ugettext("Spanish")),
    ("fr", ugettext("French")),
    ("en", ugettext("English")),
    ("ar", ugettext("Arabic")),
)

USE_I18N = True
USE_TZ = True

TEMPLATES[0]["OPTIONS"]["libraries"]["i18n"] = "django.templatetags.i18n"