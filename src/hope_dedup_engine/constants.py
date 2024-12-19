from enum import Enum


class FacialError(Enum):
    GENERIC_ERROR = 999.0
    NO_FACE_DETECTED = 998.0
    MULTIPLE_FACES_DETECTED = 997.0
    NO_FILE_FOUND = 996.0

    @property
    def code(self) -> int:
        return self.value


def is_facial_error(value):
    if isinstance(value, str):
        return value in FacialError.__members__
    if isinstance(value, float):
        return value in FacialError._value2member_map_
    return False


# NO_FACE_DETECTED: Final[str] = "NO_FACE_DETECTED"
# MULTIPLE_FACES_DETECTED: Final[str] = "MULTIPLE_FACE_DETECTED"
# FILE_ERROR: Final[str] = "GENERIC_ERROR"
# ERRORS: Final[list[str]] = [NO_FACE_DETECTED, MULTIPLE_FACES_DETECTED, FILE_ERROR]

# NO_ENCODING: Final[float] = 999
