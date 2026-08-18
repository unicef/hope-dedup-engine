from django.contrib import admin
from hope_api_auth.admin import APITokenAdmin as BaseAPITokenAdmin
from hope_api_auth.admin import APITokenForm as BaseAPITokenForm

from hope_dedup_engine.apps.api.models import APIToken


class APITokenForm(BaseAPITokenForm):
    class Meta(BaseAPITokenForm.Meta):
        model = APIToken


@admin.register(APIToken)
class APITokenAdmin(BaseAPITokenAdmin):
    form = APITokenForm
