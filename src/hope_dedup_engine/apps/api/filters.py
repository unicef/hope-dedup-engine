from django_filters import rest_framework as filters

from hope_dedup_engine.apps.api.models import Encoding, Finding


class FindingFilter(filters.FilterSet):
    status_code = filters.ChoiceFilter(
        field_name="status_code",
        choices=Encoding.StatusCode.choices,
        help_text="Filter by status code",
    )
    updated_after = filters.DateTimeFilter(
        field_name="updated_at",
        lookup_expr="gte",
        help_text="Filter by updated_at >= datetime (ISO 8601: 2025-09-30T10:00:00Z)",
    )
    updated_before = filters.DateTimeFilter(
        field_name="updated_at",
        lookup_expr="lte",
        help_text="Filter by updated_at <= datetime (ISO 8601: 2025-09-30T10:00:00Z)",
    )

    class Meta:
        model = Finding
        fields = []
