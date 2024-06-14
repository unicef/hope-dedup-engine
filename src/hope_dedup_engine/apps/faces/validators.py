from django.core.exceptions import ValidationError


class IgnorePairsValidator:
    @staticmethod
    def validate(ignore: tuple[tuple[str, str], ...]) -> set[tuple[str, str]]:
        if not ignore:
            return set()
        if not (
            isinstance(ignore, tuple)
            and all(
                all(
                    (
                        isinstance(pair, tuple),
                        len(pair) == 2,
                        all(isinstance(item, str) and item for item in pair),
                    )
                )
                for pair in ignore
            )
        ):
            raise ValidationError(
                "Invalid format. Expected a tuple of tuples, each containing exactly two strings."
            )

        result_set = set()
        for pair in ignore:
            result_set.add(pair)
            result_set.add((pair[1], pair[0]))
        return result_set
