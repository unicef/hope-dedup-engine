from django.contrib import admin

from .config import ConfigAdmin  # noqa
from .deduplicationset import DeduplicationSetAdmin  # noqa
from .duplicate import DuplicateAdmin  # noqa
from .hdetoken import HDETokenAdmin  # noqa
from .image import ImageAdmin  # noqa

admin.site.site_header = "HOPE Dedup Engine"
admin.site.site_title = "HOPE Deduplication Admin"
admin.site.index_title = "Welcome to the HOPE Deduplication Engine Admin"
