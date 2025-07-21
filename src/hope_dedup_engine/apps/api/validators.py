from constance import config
from jsonschema import Draft202012Validator, validators


def extend_with_default(validator_class):
    validate_properties = validator_class.VALIDATORS["properties"]

    def set_defaults(validator, properties, instance, schema):
        for prop, subschema in properties.items():
            if "default" in subschema:
                default_value = subschema["default"]
                if isinstance(default_value, str) and default_value.startswith("constance.config."):
                    config_name = default_value.split(".")[-1]
                    default_value = getattr(config, config_name, None)

                instance.setdefault(prop, default_value)

        yield from validate_properties(
            validator,
            properties,
            instance,
            schema,
        )

    return validators.extend(
        validator_class,
        {"properties": set_defaults},
    )


DefaultValidatingValidator = extend_with_default(Draft202012Validator)
