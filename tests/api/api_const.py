from hope_dedup_engine.apps.api.const import (
    BULK_IMAGE_LIST,
    DEDUPLICATION_SET_LIST,
    DUPLICATE_LIST,
    IGNORED_FILENAME_LIST,
    IGNORED_REFERENCE_PK_LIST,
    IMAGE_LIST,
)

JSON = "json"
LIST = "list"
DETAIL = "detail"
DEDUPLICATION_SET_LIST_VIEW = f"{DEDUPLICATION_SET_LIST}-{LIST}"
DEDUPLICATION_SET_DETAIL_VIEW = f"{DEDUPLICATION_SET_LIST}-{DETAIL}"
DEDUPLICATION_SET_PROCESS_VIEW = f"{DEDUPLICATION_SET_LIST}-process"
IMAGE_LIST_VIEW = f"{IMAGE_LIST}-{LIST}"
IMAGE_DETAIL_VIEW = f"{IMAGE_LIST}-{DETAIL}"
BULK_IMAGE_LIST_VIEW = f"{BULK_IMAGE_LIST}-{LIST}"
BULK_IMAGE_CLEAR_VIEW = f"{BULK_IMAGE_LIST}-clear"
DUPLICATE_LIST_VIEW = f"{DUPLICATE_LIST}-{LIST}"
IGNORED_REFERENCE_PK_LIST_VIEW = f"{IGNORED_REFERENCE_PK_LIST}-{LIST}"
IGNORED_FILENAME_LIST_VIEW = f"{IGNORED_FILENAME_LIST}-{LIST}"
