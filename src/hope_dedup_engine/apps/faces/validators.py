from django.forms import CharField, ValidationError


class MeanValuesTupleField(CharField):
    def to_python(self, value):
        try:
            values = tuple(map(float, value.split(", ")))
            if len(values) != 3:
                raise ValueError("The tuple must have exactly three elements.")
            if not all(-255 <= v <= 255 for v in values):
                raise ValueError(
                    "Each value in the tuple must be between -255 and 255."
                )
            return values
        except Exception as e:
            raise ValidationError(
                """
                Enter a valid tuple of three float values separated by commas and spaces, e.g. '0.0, 0.0, 0.0'.
                Each value must be between -255 and 255.
                """
            ) from e

    def prepare_value(self, value):
        if isinstance(value, tuple):
            return ", ".join(map(str, value))
        return super().prepare_value(value)
