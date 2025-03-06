class DeduplicationSetLightQuerysetMixin:
    """
    Optimizes queryset by excluding heavy fields ('encodings') from DeduplicationSet.
    Prevents memory overload in Django admin queries.
    """

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("deduplication_set").defer("deduplication_set__encodings")
