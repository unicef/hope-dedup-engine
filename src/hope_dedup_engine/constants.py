from enum import Enum


class FacialError(Enum):
    GENERIC_ERROR = 999
    NO_FACE_DETECTED = 998
    MULTIPLE_FACES_DETECTED = 997
    NO_FILE_FOUND = 996

    @property
    def code(self) -> int:
        return self.value


def is_facial_error(value):
    if isinstance(value, str):
        return value in FacialError.__members__
    if isinstance(value, int):
        return value in FacialError._value2member_map_
    return False
