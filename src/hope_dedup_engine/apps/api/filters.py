from django_filters import rest_framework as filters
from django.db.models import Q, QuerySet
from constance import config

from hope_dedup_engine.apps.api.exceptions import TooManyReferencePksException
from hope_dedup_engine.apps.api.models import Finding


class CharInFilter(filters.BaseInFilter, filters.CharFilter):
    pass


class FindingFilter(filters.FilterSet):
    reference_pk = CharInFilter(method="filter_by_references", help_text="Filter by one or more reference pks")
    status_code = filters.NumberFilter(field_name="status_code", help_text="Filter by status code")
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

    def filter_by_references(self, qs: QuerySet[Finding], name: str, values: list[str]) -> QuerySet[Finding]:
        if not values:
            return qs

        if len(values) > config.MAX_REFERENCE_PKS_ALLOWED_FOR_FINDINGS:
            raise TooManyReferencePksException()

        return qs.filter(Q(first_encoding__reference_pk__in=values) | Q(second_encoding__reference_pk__in=values))
