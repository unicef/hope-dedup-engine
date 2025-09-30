from django_filters import rest_framework as filters
from django.db.models import Q, QuerySet

from hope_dedup_engine.apps.api.models import Finding


class FindingFilter(filters.FilterSet):
    reference_pk = filters.CharFilter(method="filter_by_reference", help_text="Filters by reference pk")
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

    def filter_by_reference(self, qs: QuerySet[Finding], name: str, value: str) -> QuerySet[Finding]:
        return qs.filter(Q(first_reference_pk=value) | Q(second_reference_pk=value))
