# Findings and Statuses

Findings are the output of a deduplication run. They are available from

```
GET /deduplication_sets/{id}/findings/
```

once the set is in **`Deduplicated`** state (in any other state the endpoint returns an empty list).

## Response format

```json
{
    "count": 12,
    "next": "https://.../findings/?page=2",
    "previous": null,
    "results": [
        {
            "first": {"reference_pk": "IND-0001"},
            "second": {"reference_pk": "IND-0042"},
            "score": 0.87,
            "status_code": 200,
            "config": {
                "duplicate_confidence_threshold": 0.5,
                "face_detection_confidence_threshold": 0.9,
                "...": "..."
            },
            "updated_at": "2026-07-13T10:05:40Z"
        },
        {
            "first": {"reference_pk": "IND-0007"},
            "second": {"reference_pk": ""},
            "score": 0.0,
            "status_code": 412,
            "config": {"...": "..."},
            "updated_at": "2026-07-13T10:04:11Z"
        }
    ]
}
```

There are two kinds of findings, distinguished by `status_code`:

1. **Duplicate pairs** (`status_code: 200`) — `first` and `second` identify the two matching images by *your* `reference_pk` values, and `score` is the match confidence (0–1; higher = more certain the two faces are the same person). Pairs may include images from previously **approved** sets in the group — that's how new records are matched against the already-accepted population.
2. **Per-image problems** (`status_code` ≠ 200) — `second.reference_pk` is empty and `score` is 0. These tell you which images could not participate in deduplication and why, so you can ask for a better photo.

Every finding carries a `config` snapshot of the [settings](configuration.md) that were active when it was produced.

## Image status codes

| Code | Label | Meaning | Typical remedy |
|------|-------|---------|----------------|
| 200 | Deduplication success | The finding is a duplicate pair. | — |
| 404 | No file found | The registered image file could not be found in storage. | Fix the path or re-upload the file. |
| 412 | No face detected | Neither OFIQ nor the face detector found a face. | Retake the photo. |
| 416 | Face not accepted | A face was found but its detection confidence is below `face_detection_confidence_threshold`. | Better photo, or lower the threshold. |
| 418 | Bad image quality | The image failed one of the enabled OFIQ quality thresholds. | Better photo, or adjust quality thresholds. |
| 429 | Multiple faces detected | More than one face in the image; the engine only handles single-subject portraits. | Crop or retake the photo. |
| 500 | Generic error | Unexpected error while processing this image (details go to Sentry). | Retry processing; contact the operators if it persists. |

## Pagination and filtering

Results are paginated (`page` / `page_size` query parameters; default page size 1000, maximum 10000) and ordered by most recently updated first. Available filters:

| Query parameter | Example | Effect |
|-----------------|---------|--------|
| `status_code` | `?status_code=200` | Only duplicate pairs (or only a specific problem type). |
| `updated_after` | `?updated_after=2026-07-13T10:00:00Z` | Findings updated at or after the given ISO 8601 datetime. |
| `updated_before` | `?updated_before=2026-07-13T11:00:00Z` | Findings updated at or before the given datetime. |

A common pattern is to fetch duplicate pairs and problems separately:

```console
$ http GET "$BASE/deduplication_sets/{id}/findings/?status_code=200"   # duplicates
$ http GET "$BASE/deduplication_sets/{id}/findings/?status_code=412"   # no-face images
```
