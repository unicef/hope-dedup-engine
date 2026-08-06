"""Stateless export of a deduplication set collection's embeddings to the `embeddings` storage.

No DB bookkeeping: the zip blob itself is the export state. The blob only
becomes visible on the storage once fully committed (Azure semantics), so its
existence is the "ready" signal. On failure the task writes a small
`<key>.error.json` sibling blob so the status endpoint can report the error.

One zip per export (typically one per country office), in one of two formats:

- ``npy`` (default): ``embeddings.npy`` — a single float32 matrix of all
  successful embeddings — plus ``index.jsonl`` mapping every registered image
  (including failed ones) to its matrix row (``row: null`` for failures).
- ``jsonl``: ``encodings.jsonl`` with one self-describing line per registered
  image, embedding inline.

Both contain a ``manifest.json`` with per-set boundaries and counts. All
writers stream row-by-row (server-side DB cursor, zip member streams, and a
disk-backed memmap for the npy matrix), so worker RAM stays constant
regardless of export size; scratch disk usage is ~2x the final zip.
"""

import json
import tempfile
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any, BinaryIO, Iterator
from uuid import uuid4

import numpy as np
import sentry_sdk
from celery import shared_task
from django.core.files import File
from django.core.files.base import ContentFile
from django.core.files.storage import Storage, storages
from django.utils import timezone

from hope_dedup_engine.apps.api.deduplication.config import DeduplicationSetConfig
from hope_dedup_engine.apps.api.models import DeduplicationSet, Encoding

EXPORT_FORMAT_NPY = "npy"
EXPORT_FORMAT_JSONL = "jsonl"
EXPORT_FORMATS = (EXPORT_FORMAT_NPY, EXPORT_FORMAT_JSONL)

EXPORTS_PREFIX = "exports"
EMBEDDINGS_MEMBER = "embeddings.npy"
INDEX_MEMBER = "index.jsonl"
ENCODINGS_MEMBER = "encodings.jsonl"
MANIFEST_MEMBER = "manifest.json"
ERROR_SUFFIX = ".error.json"


class ExportError(Exception):
    """Data problem that makes the requested export impossible."""


def get_embeddings_storage() -> Storage:
    return storages["embeddings"]


def export_key_prefix(system_pk: int) -> str:
    return f"{EXPORTS_PREFIX}/{system_pk}/"


def build_export_key(system_pk: int, reference_pk: str, export_format: str) -> str:
    """Versioned, collision-free blob key. Clients must treat it as opaque."""
    timestamp = timezone.now().strftime("%Y%m%dT%H%M%SZ")
    return (
        f"{EXPORTS_PREFIX}/{system_pk}/{reference_pk}/{reference_pk}-{timestamp}-{uuid4().hex[:8]}.{export_format}.zip"
    )


def error_key(key: str) -> str:
    return f"{key}{ERROR_SUFFIX}"


def _encoding_status_code(row: dict[str, Any]) -> int | None:
    # Success is not stored as a status code: a successful encoding has an
    # embedding and a null embedding_status_code (encoding_embedding_or_status
    # constraint).
    if row["embedding"] is not None:
        return Encoding.StatusCode.DEDUPLICATE_SUCCESS.value
    return row["embedding_status_code"]


def _iter_set_rows(deduplication_set: DeduplicationSet) -> Iterator[dict[str, Any]]:
    return (
        deduplication_set.encoding_set.order_by("created_at", "id")
        .values("reference_pk", "filename", "embedding", "embedding_status_code")
        .iterator()
    )


def _set_entry(deduplication_set: DeduplicationSet, counts: Counter) -> dict[str, Any]:
    return {
        "deduplication_set_id": str(deduplication_set.pk),
        "group_reference_pk": deduplication_set.group.reference_pk,
        "image_count": sum(counts.values()),
        "counts_by_status_code": dict(counts),
    }


def _model_version(deduplication_set: DeduplicationSet) -> str:
    return DeduplicationSetConfig.from_deduplication_set(deduplication_set).recognition_model


def _write_jsonl(
    zip_file: zipfile.ZipFile,
    deduplication_sets: list[DeduplicationSet],
    manifest: dict[str, Any],
) -> None:
    """Single CO-wide `encodings.jsonl` member with embeddings inline."""
    line_no = 0
    with zip_file.open(ENCODINGS_MEMBER, "w") as member:
        for deduplication_set in deduplication_sets:
            model_version = _model_version(deduplication_set)
            counts: Counter[str] = Counter()
            start_line = line_no
            for row in _iter_set_rows(deduplication_set):
                status_code = _encoding_status_code(row)
                line = {
                    "reference_pk": row["reference_pk"],
                    "filename": row["filename"],
                    "embedding": row["embedding"],
                    "status_code": status_code,
                    "model_version": model_version,
                }
                member.write(json.dumps(line).encode() + b"\n")
                counts[str(status_code)] += 1
                line_no += 1
            manifest["sets"].append(
                _set_entry(deduplication_set, counts)
                | {"model_version": model_version, "line_range": [start_line, line_no]}
            )


def _write_npy(
    zip_file: zipfile.ZipFile,
    deduplication_sets: list[DeduplicationSet],
    manifest: dict[str, Any],
    scratch_dir: str,
) -> None:
    """CO-wide float32 matrix (disk-backed memmap) + `index.jsonl` row mapping."""
    model_versions = {_model_version(ds) for ds in deduplication_sets}
    if len(model_versions) > 1:
        raise ExportError(
            "Cannot build a single embeddings matrix from mixed recognition models: "
            f"{', '.join(sorted(model_versions))}. Use the jsonl format instead."
        )
    manifest["model_version"] = model_versions.pop() if model_versions else None

    encodings = Encoding.objects.filter(deduplication_set__in=deduplication_sets, embedding__isnull=False)
    n_success = encodings.count()
    first_embedding = encodings.values_list("embedding", flat=True).first()
    dim = len(first_embedding) if first_embedding is not None else None
    manifest["dim"] = dim

    matrix = None
    matrix_path = Path(scratch_dir) / EMBEDDINGS_MEMBER
    if n_success:
        matrix = np.lib.format.open_memmap(matrix_path, mode="w+", dtype=np.float32, shape=(n_success, dim))

    row_no = 0
    with zip_file.open(INDEX_MEMBER, "w") as member:
        for deduplication_set in deduplication_sets:
            counts: Counter[str] = Counter()
            start_row = row_no
            for row in _iter_set_rows(deduplication_set):
                status_code = _encoding_status_code(row)
                matrix_row = None
                if row["embedding"] is not None:
                    if len(row["embedding"]) != dim:
                        raise ExportError(
                            f"Inconsistent embedding size for '{row['reference_pk']}': "
                            f"expected {dim}, got {len(row['embedding'])}."
                        )
                    matrix[row_no] = row["embedding"]
                    matrix_row = row_no
                    row_no += 1
                line = {
                    "reference_pk": row["reference_pk"],
                    "filename": row["filename"],
                    "status_code": status_code,
                    "row": matrix_row,
                }
                member.write(json.dumps(line).encode() + b"\n")
                counts[str(status_code)] += 1
            manifest["sets"].append(_set_entry(deduplication_set, counts) | {"row_range": [start_row, row_no]})

    if matrix is not None:
        matrix.flush()
        del matrix
        # Float data barely deflates; storing it uncompressed makes both the
        # export and the download much faster.
        zip_file.write(matrix_path, EMBEDDINGS_MEMBER, compress_type=zipfile.ZIP_STORED)


def _build_zip(
    tmp: BinaryIO,
    scratch_dir: str,
    manifest: dict[str, Any],
    deduplication_sets: list[DeduplicationSet],
) -> None:
    export_format = manifest["format"]
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zip_file:
        if export_format == EXPORT_FORMAT_NPY:
            _write_npy(zip_file, deduplication_sets, manifest, scratch_dir)
        else:
            _write_jsonl(zip_file, deduplication_sets, manifest)
        totals: Counter[str] = Counter()
        for entry in manifest["sets"]:
            totals.update(entry["counts_by_status_code"])
        manifest["total_image_count"] = sum(totals.values())
        manifest["total_counts_by_status_code"] = dict(totals)
        zip_file.writestr(MANIFEST_MEMBER, json.dumps(manifest, indent=2))


@shared_task
def export_encodings(
    key: str, reference_pk: str, deduplication_set_ids: list[str], export_format: str = EXPORT_FORMAT_NPY
) -> dict[str, Any]:
    """Zip the embeddings of the given sets into `key` on the embeddings storage."""
    storage = get_embeddings_storage()
    try:
        by_id = {
            str(ds.pk): ds
            for ds in DeduplicationSet.objects.filter(pk__in=deduplication_set_ids).select_related("group")
        }
        # Deterministic member/row order: sets in request order.
        deduplication_sets = [by_id[set_id] for set_id in deduplication_set_ids if set_id in by_id]

        manifest: dict[str, Any] = {
            "reference_pk": reference_pk,
            "key": key,
            "format": export_format,
            "created_at": timezone.now().isoformat(),
            "sets": [],
        }
        with tempfile.TemporaryDirectory() as scratch_dir, tempfile.TemporaryFile() as tmp:
            _build_zip(tmp, scratch_dir, manifest, deduplication_sets)
            tmp.seek(0)
            storage.save(key, File(tmp))
        return {
            "key": key,
            "sets": len(deduplication_sets),
            "images": manifest["total_image_count"],
        }
    except Exception as e:
        payload = {
            "reference_pk": reference_pk,
            "error": f"{type(e).__name__}: {e}"[:1000],
            "timestamp": timezone.now().isoformat(),
        }
        storage.save(error_key(key), ContentFile(json.dumps(payload).encode()))
        sentry_sdk.capture_exception(e)
        raise
