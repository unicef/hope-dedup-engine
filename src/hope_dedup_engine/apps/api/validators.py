from typing import Any

from django.core.exceptions import ValidationError

from constance import settings as constance_settings


def validate_constance_config(data: dict) -> None:
    """
    Validates a configuration dictionary against the Constance settings.

    Args:
        data (dict): The configuration dictionary to validate.
            Keys should correspond to the parameter names defined in `constance_settings.CONFIG`.
            Values should meet the constraints defined in the Constance settings.

    Raises:
        ValidationError: If the dictionary contains unknown keys, invalid values,
            or values that do not match the expected constraints.
    """
    errors = []
    config = {k.lower(): v for k, v in constance_settings.CONFIG.items()}
    fields = constance_settings.ADDITIONAL_FIELDS

    errors.extend(_find_unknown_keys(data.keys(), config.keys()))

    for key, (_, _, field_type) in config.items():
        if key in data:
            value = data[key]

            if field_type in fields:
                _, field_kwargs = fields[field_type]
                match field_kwargs:
                    case {"choices": choices}:
                        if error := _validate_choices(key, value, choices):
                            errors.append(error)
                    case {"min_value": min_value, "max_value": max_value}:
                        if error := _validate_range(key, value, min_value, max_value):
                            errors.append(error)
            else:
                if error := _validate_other_fieldtype(key, value, field_type):
                    errors.append(error)

    if errors:
        raise ValidationError(errors)


def _find_unknown_keys(keys: list[str], valid_keys: list[str]) -> list[str]:
    return [f"Unknown parameter: '{k}'." for k in keys if k not in valid_keys]


def _validate_choices(key: str, value: Any, choices: tuple[str]) -> str | None:
    allowed_values = [choice[0] for choice in choices]
    if value not in allowed_values:
        return f"Invalid value '{key}:{value}'. Expected one of {allowed_values}."


def _validate_range(
    key: str, value: float, min_value: float, max_value: float
) -> str | None:
    if not isinstance(value, (int, float)):
        return f"Invalid value '{key}:{value}'. Expected a number."
    if not (min_value <= value <= max_value):
        return f"Invalid value '{key}:{value}'. Must be between {min_value} and {max_value}."


def _validate_other_fieldtype(key: str, value: Any, expected_type: type) -> str | None:
    try:
        expected_type(value)
    except Exception:
        return f"Invalid value '{key}:{value}'. Expected {expected_type.__name__} type."
