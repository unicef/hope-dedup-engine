from django.conf import settings

from constance import config
from jsonschema import Draft202012Validator, validators

settings_schema: dict = {
    "type": "object",
    "properties": {
        "detection": {
            "type": "object",
            "properties": {
                "confidence": {
                    "type": "number",
                    "exclusiveMinimum": 0,
                    "maximum": 1.0,
                    "default": "constance.config.FACE_DETECTION_CONFIDENCE",
                },
            },
            "default": {},
        },
        "recognition": {
            "type": "object",
            "properties": {
                "num_jitters": {
                    "type": "integer",
                    "minimum": 1,
                    "default": "constance.config.FACE_ENCODINGS_NUM_JITTERS",
                },
                "model": {
                    "type": "string",
                    "enum": tuple(
                        ch[0]
                        for ch in settings.CONSTANCE_ADDITIONAL_FIELDS.get(
                            "face_encodings_model"
                        )[1].get("choices")
                    ),
                    "default": "constance.config.FACE_ENCODINGS_MODEL",
                },
                "preprocessors": {
                    type: "array",
                    "items": {
                        "type": "string",
                        "enum": ["contrast"],
                    },
                    "uniqueItems": True,
                    "default": [],
                },
            },
            "default": {},
        },
        "duplicates": {
            "type": "object",
            "properties": {
                "tolerance": {
                    "type": "number",
                    "exclusiveMinimum": 0,
                    "maximum": 1.0,
                    "default": "constance.config.FACE_DISTANCE_THRESHOLD",
                },
            },
            "default": {},
        },
    },
}


def extend_with_default(validator_class):
    validate_properties = validator_class.VALIDATORS["properties"]

    def set_defaults(validator, properties, instance, schema):
        for property, subschema in properties.items():

            if "default" in subschema:
                default_value = subschema["default"]
                if isinstance(default_value, str) and default_value.startswith(
                    "constance.config."
                ):
                    config_name = default_value.split(".")[-1]
                    default_value = getattr(config, config_name, None)

                instance.setdefault(property, default_value)

        for error in validate_properties(
            validator,
            properties,
            instance,
            schema,
        ):
            yield error

    return validators.extend(
        validator_class,
        {"properties": set_defaults},
    )


DefaultValidatingValidator = extend_with_default(Draft202012Validator)
