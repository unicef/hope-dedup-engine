# Exporting Embeddings

After running sets with [`?encode_only=true`](workflow.md#4-start-processing) you can bundle the embeddings of many sets into a single zip and share it via a **signed URL** — nothing large ever crosses the API. A typical use is one export per country office, covering all of its 10k-image chunks.

The export is **stateless** on the engine side: the zip blob on the dedicated `embeddings` storage *is* the state. You must persist the blob key returned when you request the export; the engine keeps no export records.

## 1. Request an export

```console
$ http POST $BASE/encodings_exports/ \
    reference_pk=afghanistan \
    deduplication_set_ids:='["3fa85f64-...", "8c1a2b3c-..."]' \
    format=npy
```

```json
{
    "key": "exports/1/afghanistan/afghanistan-20260806T120000Z-a1b2c3d4.npy.zip",
    "state": "pending"
}
```

- `reference_pk` is your grouping label (e.g. a country office slug); it must be a slug (letters, digits, `-`, `_`).
- `format` selects the [zip payload](#zip-contents): `npy` (default, compact binary matrix) or `jsonl` (self-describing text). The chosen format is embedded in the returned key.
- Every set must belong to your system and be in `Encoded` state or later, otherwise **409** (not yet encoded) or **400** (unknown/foreign set ids).
- Returns **202** with the versioned blob `key`. **Treat the key as opaque and store it** — it is how you poll and how the zip is found. Every POST starts a fresh export under a new key; requests never collide.

## 2. Poll the status

```console
$ http GET "$BASE/encodings_exports/status/?key=exports/1/afghanistan/afghanistan-20260806T120000Z-a1b2c3d4.zip"
```

| Response | Meaning |
|----------|---------|
| `{"state": "pending"}` | Zip not built yet. Also returned for a key that was never submitted — you own the bookkeeping. If pending persists past a sensible timeout, re-request the export. |
| `{"state": "ready", "url": "https://...sig=...", "expires_at": "..."}` | Done. `url` is a signed download URL. |
| `{"state": "failed", "error": "..."}` | The export task failed; re-request after fixing the cause. |

The URL is **re-signed on every status call** with a configurable validity (`EMBEDDINGS_EXPORT_URL_TTL`, default 7 days) — poll again anytime to renew an expired URL without rebuilding the zip. Keys outside your system's namespace return **404**.

## Zip contents

Both formats account for **every registered image — including failed ones**, so no cross-referencing with `findings/` is needed, and both include a `manifest.json` with the `reference_pk`, creation timestamp, per-set entries (`deduplication_set_id`, `group_reference_pk`, `image_count`, `counts_by_status_code`, and the set's row/line range) plus grand totals.

`status_code` is `200` for successfully encoded images, otherwise one of the [image status codes](findings-and-statuses.md#image-status-codes).

### `npy` (default)

```
embeddings.npy   # float32 matrix (n_success x dim), one row per successful embedding
index.jsonl      # one line per registered image, mapping it to its matrix row
manifest.json
```

Load with `numpy.load()` — rows follow the order of `index.jsonl` lines that have a non-null `row`:

```json
{"reference_pk": "IND-0001", "filename": "path/in/hope/storage.jpg", "status_code": 200, "row": 0}
{"reference_pk": "IND-0007", "filename": "path/in/hope/storage2.jpg", "status_code": 412, "row": null}
```

The manifest carries the shared `model_version` and the matrix `dim`. Because a single matrix can only hold one embedding size, an `npy` export of sets configured with **different recognition models fails** — use `jsonl` for those, or export per model. If no image encoded successfully, `embeddings.npy` is omitted and `dim` is `null`.

This format is roughly 8x smaller than `jsonl` (4 bytes per float instead of ~17 characters of JSON) and loads directly into numpy without parsing.

### `jsonl`

```
encodings.jsonl  # one self-describing line per registered image, embedding inline
manifest.json
```

```json
{"reference_pk": "IND-0001", "filename": "path/in/hope/storage.jpg", "embedding": [0.0123, -0.0456], "status_code": 200, "model_version": "Facenet512"}
{"reference_pk": "IND-0007", "filename": "path/in/hope/storage2.jpg", "embedding": null, "status_code": 412, "model_version": "Facenet512"}
```

`model_version` is per line, so mixed recognition models are fine — receivers need it to check embedding compatibility.

## Operational notes

- The zip lands on the `embeddings` storage (`FILE_STORAGE_EMBEDDINGS`), separate from images, so signed URLs can only ever expose exports.
- Old export blobs are not deleted automatically; configure an Azure lifecycle rule on the container (e.g. delete after N days).
- Sizing: a 512-float embedding is 2 KB as float32 (`npy`) or ~9 KB as JSON (`jsonl`); 500k images ≈ 1 GB (`npy`) vs ≈ 4.5 GB (`jsonl`). The `.npy` member is stored uncompressed in the zip (float data barely deflates), and the export task streams everything through disk, so worker memory stays flat regardless of size.
