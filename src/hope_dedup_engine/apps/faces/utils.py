from hope_dedup_engine.apps.api.models import Image


def is_facial_error(value):
    if isinstance(value, (int, str)):
        return value not in {
            Image.StatusCode.DEDUPLICATE_SUCCESS,
            Image.StatusCode.DEDUPLICATE_SUCCESS.name,
            Image.StatusCode.DEDUPLICATE_SUCCESS.label,
        } and value in (
            Image.StatusCode.values
            + Image.StatusCode.names
            + [choice.label for choice in Image.StatusCode]
        )
    return False
