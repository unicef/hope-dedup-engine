from hope_dedup_engine.apps.biographic.contracts import PAYLOAD_FIELDS, BiographicPayload


def make_payload(reference_pk: str, **fields) -> BiographicPayload:
    """Build a payload, defaulting every scoreable field the caller does not set."""
    values: dict = dict.fromkeys(PAYLOAD_FIELDS)
    values.update(fields)
    return BiographicPayload(reference_pk=reference_pk, **values)
