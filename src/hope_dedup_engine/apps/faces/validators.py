from django.core.exceptions import ValidationError


class IgnorePairsValidator:
    @staticmethod
    def validate(ignore: tuple[tuple[str, str], ...]) -> set[tuple[str, str]]:
        if not ignore:
            return set()
        if not (
            isinstance(ignore, list)
            and all(
                all(
                    (
                        isinstance(pair, list),
                        len(pair) == 2,
                        all(isinstance(item, str) and item for item in pair),
                    )
                )
                for pair in ignore
            )
        ):
            raise ValidationError("Invalid format for ignore pairs.")

        result_set = set()
        for pair in ignore:
            result_set.add(tuple(pair))
            result_set.add(tuple(reversed(pair)))
        return result_set
