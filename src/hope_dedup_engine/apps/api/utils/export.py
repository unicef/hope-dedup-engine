import csv
from collections.abc import Iterator, Sequence
from typing import Any

from django.db.models import QuerySet
from django.http import StreamingHttpResponse
from django.utils.http import content_disposition_header

DEFAULT_FINDING_FIELDS: tuple[str, ...] = (
    "pk",
    "first_encoding__reference_pk",
    "second_encoding__reference_pk",
    "score",
    "status_code",
)


class _Echo:
    """File-like adapter for csv.writer to support streaming responses."""

    def write(self, value: str) -> str:
        return value


def export_as_csv(
    queryset: QuerySet[Any],
    filename: str,
    *,
    fields: Sequence[str] = DEFAULT_FINDING_FIELDS,
    headers: Sequence[str] | None = None,
    chunk_size: int = 2000,
) -> StreamingHttpResponse:
    """Stream a queryset as CSV without loading all rows into memory."""
    if headers is None:
        headers = fields
    values_iter = queryset.values_list(*fields).iterator(chunk_size=chunk_size)
    writer = csv.writer(_Echo())

    def stream() -> Iterator[str]:
        yield writer.writerow(headers)
        for row in values_iter:
            yield writer.writerow(row)

    response = StreamingHttpResponse(stream(), content_type="text/csv; charset=utf-8")
    response.headers["Content-Disposition"] = content_disposition_header(as_attachment=True, filename=filename)
    return response
