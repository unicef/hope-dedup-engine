from django_filters import rest_framework as filters

from hope_dedup_engine.apps.biographic.models import BiographicFinding


class BiographicFindingFilter(filters.FilterSet):
    min_score = filters.NumberFilter(
        field_name="score",
        lookup_expr="gte",
        help_text="Only findings scoring at least this.",
    )
    scope = filters.ChoiceFilter(
        field_name="scope",
        choices=BiographicFinding.Scope.choices,
        help_text="Only findings within the set (batch) or against the approved population.",
    )
    reference_pk = filters.CharFilter(
        field_name="record__reference_pk",
        help_text="Only findings for this record of the set.",
    )

    class Meta:
        model = BiographicFinding
        fields: list[str] = []
