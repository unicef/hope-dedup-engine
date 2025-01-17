from hope_dedup_engine.apps.api.models import Finding


def is_facial_error(value):
    if isinstance(value, (int, str)):
        return value not in {
            Finding.StatusCode.DEDUPLICATE_SUCCESS,
            Finding.StatusCode.DEDUPLICATE_SUCCESS.name,
            Finding.StatusCode.DEDUPLICATE_SUCCESS.label,
        } and value in (
            Finding.StatusCode.values
            + Finding.StatusCode.names
            + [choice.label for choice in Finding.StatusCode]
        )
    return False
