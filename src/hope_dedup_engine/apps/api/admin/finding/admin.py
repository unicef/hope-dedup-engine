from django.contrib.admin import register
from django.urls import path, reverse
from adminfilters.autocomplete import LinkedAutoCompleteFilter
from adminfilters.filters import DjangoLookupFilter, NumberFilter
from admin_extra_buttons.api import link

from hope_dedup_engine.apps.api.models import Finding
from hope_dedup_engine.apps.api.admin.finding.views import FindingImageView, FindingPreviewView
from hope_dedup_engine.apps.core.permissions import can
from hope_dedup_engine.apps.api.admin.base import BaseModelAdmin


@register(Finding)
class FindingAdmin(BaseModelAdmin):
    list_display = (
        "id",
        "score",
        "deduplication_set",
        "status_code",
        "created_at",
    )
    readonly_fields = (
        "id",
        "score",
        "first_encoding",
        "second_encoding",
        "deduplication_set",
        "status_code",
        "config",
        "created_at",
        "updated_at",
    )
    list_filter = (
        ("deduplication_set__group", LinkedAutoCompleteFilter.factory(parent=None)),
        ("deduplication_set", LinkedAutoCompleteFilter.factory(parent="deduplication_set__group")),
        ("score", NumberFilter),
        "status_code",
        DjangoLookupFilter,
    )
    list_select_related = ("deduplication_set",)
    search_fields = (
        "first_encoding__reference_pk",
        "second_encoding__reference_pk",
        "deduplication_set__name",
        "deduplication_set__group__pk",
        "deduplication_set__group__name",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return obj is not None

    def get_urls(self):
        return [
            path(
                "<int:pk>/detail/",
                self.admin_site.admin_view(FindingPreviewView.as_view()),
                name="api_finding_details",
            ),
            path(
                "image/<path:filename>/",
                self.admin_site.admin_view(FindingImageView.as_view()),
                name="api_finding_image",
            ),
            *super().get_urls(),
        ]

    @link(
        change_form=True,
        change_list=False,
        permission=can.api.view_finding_details,
        html_attrs={"target": "_blank", "rel": "noopener noreferrer"},
    )
    def details(self, button) -> None:
        """Add a button that opens a separate window with both images."""
        original: Finding = button.context["original"]
        button.href = reverse("admin:api_finding_details", kwargs={"pk": original.pk})
