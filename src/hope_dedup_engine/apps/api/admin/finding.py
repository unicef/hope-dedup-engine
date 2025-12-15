from django.contrib.admin import ModelAdmin, register
from django.urls import path, reverse

from adminfilters.autocomplete import AutoCompleteFilter
from adminfilters.filters import DjangoLookupFilter, NumberFilter
from adminfilters.mixin import AdminFiltersMixin
from admin_extra_buttons.api import ExtraButtonsMixin, link

from hope_dedup_engine.apps.api.models import Finding
from hope_dedup_engine.apps.api.admin.views import FindingImageView, FindingPreviewView
from hope_dedup_engine.apps.api.permissions import can_view_finding_details


@register(Finding)
class FindingAdmin(ExtraButtonsMixin, AdminFiltersMixin, ModelAdmin):
    list_display = (
        "id",
        "deduplication_set",
        "score",
        "first_reference_pk",
        "second_reference_pk",
        "status_code",
        "created_at",
        "updated_at",
    )
    list_filter = (
        ("deduplication_set", AutoCompleteFilter),
        ("score", NumberFilter),
        DjangoLookupFilter,
    )
    list_select_related = ("deduplication_set",)
    search_fields = ("first_reference_pk", "second_reference_pk")

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

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return obj is not None

    @link(
        change_form=True,
        change_list=False,
        permission=can_view_finding_details,
        html_attrs={"target": "_blank", "rel": "noopener noreferrer"},
    )
    def details(self, button) -> None:
        """Add a button that opens a separate window with both images."""
        original: Finding = button.context["original"]
        button.label = "Details"
        button.href = reverse("admin:api_finding_details", kwargs={"pk": original.pk})
