from enum import Enum, auto, unique
from typing import Any


@unique
class Grant(Enum):
    def _generate_next_value_(self, start: int, count: int, last_values: list[Any]) -> Any:
        return self

    API_READ_ONLY = auto()
    API_DEDUP = auto()

    @classmethod
    def choices(cls) -> tuple[tuple[str, str], ...]:
        return tuple((member.value, member.name.replace("_", " ").title()) for member in cls)
