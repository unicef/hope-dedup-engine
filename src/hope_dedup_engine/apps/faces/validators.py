from django.core.exceptions import ValidationError


class IgnorePairsValidator:
    @staticmethod
    def validate(ignore: tuple[tuple[str, str]]) -> set[tuple[str, str]]:
        ignore = tuple(tuple(pair) for pair in ignore)
        if not ignore:
            return set()
        if all(
            isinstance(pair, tuple) and len(pair) == 2 and all(isinstance(item, str) and item for item in pair)
            for pair in ignore
        ):
            return {(item1, item2) for item1, item2 in ignore} | {(item2, item1) for item1, item2 in ignore}
        elif len(ignore) == 2 and all(isinstance(item, str) for item in ignore):
            return {(ignore[0], ignore[1]), (ignore[1], ignore[0])}
        else:
            raise ValidationError(
                "Invalid format for 'ignore'. Expected tuple of tuples each containing exactly two strings."
            )
