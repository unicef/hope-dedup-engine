import datetime
from typing import Any

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import ValidationError

from hope_dedup_engine.apps.api.models.deduplication import REFERENCE_PK_LENGTH
from hope_dedup_engine.apps.biographic.contracts import (
    BIRTH_DATE_FIELD,
    FULL_NAME_FIELD,
    IDENTITIES_FIELD,
    IDENTITY_FIELDS,
    PAYLOAD_FIELDS,
)
from hope_dedup_engine.apps.biographic.models import FULL_NAME_LENGTH

_ISO_DATE_MESSAGE = "Birth date must be an ISO 8601 date."
_STRING_MESSAGE = "Must be a string."
_REQUIRED_MESSAGE = "This field is required."
_INVALID_VALUE_MESSAGE = "Invalid value."
_UNKNOWN_FIELD_MESSAGE = "Unknown field."
_PAYLOAD_OBJECT_MESSAGE = "Payload must be an object."
_IDENTITIES_LIST_MESSAGE = "Identities must be a list of objects with string number and partner values."
_IDENTITY_OBJECT_MESSAGE = "Identity must be an object."
_UNKNOWN_IDENTITY_FIELDS_MESSAGE = "Unknown identity fields: {fields}."
_REFERENCE_PK_REQUIRED_MESSAGE = "A string reference_pk is required."
_REFERENCE_PK_LENGTH_MESSAGE = "Must be at most {limit} characters."
_DUPLICATE_REFERENCE_PK_MESSAGE = "Duplicate reference_pk in this dataset."
_RECORD_OBJECT_MESSAGE = "Record must be an object."
_REQUEST_OBJECT_MESSAGE = "Request body must be an object."
_RECORDS_LIST_MESSAGE = "Records must be a list."
_RECORDS_REQUIRED_MESSAGE = "At least one record is required."


def _is_iso8601(value: str) -> bool:
    candidate = f"{value[:-1]}+00:00" if value.endswith("Z") else value
    try:
        datetime.date.fromisoformat(candidate)
    except ValueError:
        try:
            datetime.datetime.fromisoformat(candidate)
        except ValueError:
            return False
    return True


def _validate_birth_date(value: Any) -> Any:
    if value is None:
        return None
    if not isinstance(value, str) or not _is_iso8601(value):
        raise ValidationError(_ISO_DATE_MESSAGE)
    return value


def _validate_identities(value: Any) -> Any:
    if not isinstance(value, list):
        raise ValidationError(_IDENTITIES_LIST_MESSAGE)
    cleaned: list[dict[str, str]] = []
    errors: dict[int, Any] = {}
    for index, item in enumerate(value):
        item_errors = _identity_errors(item)
        if item_errors:
            errors[index] = item_errors
        else:
            cleaned.append({key: item[key] for key in IDENTITY_FIELDS})
    if errors:
        raise ValidationError(errors)
    return cleaned


def _identity_errors(item: Any) -> dict[str, str]:
    if not isinstance(item, dict):
        return {"non_field_errors": _IDENTITY_OBJECT_MESSAGE}
    errors: dict[str, str] = {}
    unknown = sorted(set(item) - set(IDENTITY_FIELDS))
    if unknown:
        errors["non_field_errors"] = _UNKNOWN_IDENTITY_FIELDS_MESSAGE.format(fields=", ".join(unknown))
    for key in IDENTITY_FIELDS:
        if key not in item:
            errors[key] = _REQUIRED_MESSAGE
        elif not isinstance(item[key], str):
            errors[key] = _STRING_MESSAGE
    return errors


def _validate_scalar(value: Any) -> Any:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValidationError(_STRING_MESSAGE)
    return value


def _validate_field(name: str, value: Any) -> Any:
    if name == BIRTH_DATE_FIELD:
        return _validate_birth_date(value)
    if name == IDENTITIES_FIELD:
        return _validate_identities(value)
    return _validate_scalar(value)


def stored_payload(payload: Any) -> dict[str, Any]:
    """Validate a payload from ``contracts.PAYLOAD_FIELDS`` and return it unchanged."""
    if not isinstance(payload, dict):
        raise ValidationError(_PAYLOAD_OBJECT_MESSAGE)
    unknown = sorted(set(payload) - set(PAYLOAD_FIELDS))
    if unknown:
        raise ValidationError(dict.fromkeys(unknown, _UNKNOWN_FIELD_MESSAGE))
    cleaned: dict[str, Any] = {}
    errors: dict[str, Any] = {}
    for name in payload:
        try:
            cleaned[name] = _validate_field(name, payload[name])
        except ValidationError as exc:
            errors[name] = exc.detail
    if errors:
        raise ValidationError(errors)
    return cleaned


def stored_payload_for_model(payload: Any) -> dict[str, Any]:
    """Validate a payload for ``BiographicRecord.save``."""
    try:
        return stored_payload(payload)
    except ValidationError as exc:
        raise DjangoValidationError(message_from_detail(exc.detail)) from exc


def full_name_from_payload(payload: dict[str, Any]) -> str:
    """Denormalized admin-search name. Matching never reads this column."""
    value = payload.get(FULL_NAME_FIELD) or ""
    return str(value)[:FULL_NAME_LENGTH]


def message_from_detail(detail: Any) -> str:
    """Flatten a DRF validation detail to one message."""
    if isinstance(detail, list):
        if not detail:
            return _INVALID_VALUE_MESSAGE
        return message_from_detail(detail[0])
    if isinstance(detail, dict):
        if not detail:
            return _INVALID_VALUE_MESSAGE
        return message_from_detail(next(iter(detail.values())))
    return str(detail)


def field_errors(index: int | None, detail: Any) -> list[dict[str, Any]]:
    """Turn a validation detail into ``{index, field, message}`` rows."""
    if isinstance(detail, dict):
        return [
            {"index": index, "field": str(field), "message": message_from_detail(messages)}
            for field, messages in detail.items()
        ]
    return [{"index": index, "field": "payload", "message": message_from_detail(detail)}]


def _reference_pk_errors(index: int, reference_pk: Any, seen: set[str]) -> list[dict[str, Any]]:
    if not isinstance(reference_pk, str) or not reference_pk:
        return [{"index": index, "field": "reference_pk", "message": _REFERENCE_PK_REQUIRED_MESSAGE}]
    if len(reference_pk) > REFERENCE_PK_LENGTH:
        return [
            {
                "index": index,
                "field": "reference_pk",
                "message": _REFERENCE_PK_LENGTH_MESSAGE.format(limit=REFERENCE_PK_LENGTH),
            }
        ]
    if reference_pk in seen:
        return [{"index": index, "field": "reference_pk", "message": _DUPLICATE_REFERENCE_PK_MESSAGE}]
    seen.add(reference_pk)
    return []


def _parse_record(index: int, record: Any, seen: set[str]) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    if not isinstance(record, dict):
        return None, [{"index": index, "field": "record", "message": _RECORD_OBJECT_MESSAGE}]
    errors = _reference_pk_errors(index, record.get("reference_pk"), seen)
    payload = {key: value for key, value in record.items() if key != "reference_pk"}
    try:
        cleaned = stored_payload(payload)
    except ValidationError as exc:
        return None, [*errors, *field_errors(index, exc.detail)]
    if errors:
        return None, errors
    return {"reference_pk": record["reference_pk"], "payload": cleaned}, []


def parse_dataset_records(data: Any) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Validate a create-dataset body. Returns parsed records, or errors and no records."""
    if not isinstance(data, dict):
        return [], [{"index": None, "field": "records", "message": _REQUEST_OBJECT_MESSAGE}]
    if "records" not in data:
        return [], [{"index": None, "field": "records", "message": _REQUIRED_MESSAGE}]
    records = data["records"]
    if not isinstance(records, list):
        return [], [{"index": None, "field": "records", "message": _RECORDS_LIST_MESSAGE}]
    if not records:
        return [], [{"index": None, "field": "records", "message": _RECORDS_REQUIRED_MESSAGE}]
    parsed: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, record in enumerate(records):
        item, item_errors = _parse_record(index, record, seen)
        errors.extend(item_errors)
        if item is not None:
            parsed.append(item)
    if errors:
        return [], errors
    return parsed, []
