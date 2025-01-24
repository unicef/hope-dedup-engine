from enum import IntEnum


class FacialError(IntEnum):
    GENERIC_ERROR = 999
    NO_FACE_DETECTED = 998
    MULTIPLE_FACES_DETECTED = 997
    NO_FILE_FOUND = 996
