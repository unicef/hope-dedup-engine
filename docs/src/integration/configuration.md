# Configuration

Deduplication behavior is controlled by settings stored **per group**. When a group is created it snapshots the engine-wide defaults (managed by administrators, see [admin settings](../admin/settings.md)); after that, clients can read and adjust the API-exposed subset through the config endpoint.

## Reading the current settings

```console
$ http GET $BASE/deduplication_set_groups/PROGRAM-2024-001/config/
{
    "face_detection_confidence_threshold": 0.9,
    "duplicate_confidence_threshold": 0.5,
    "sharpness_threshold": 0.0,
    "dynamic_range_threshold": 0.0,
    "no_head_cover_threshold": 0.0,
    "eyes_open_threshold": 0.0,
    "inter_eye_distance_threshold": 0.0,
    "unified_quality_score_threshold": 0.0
}
```

If the group doesn't exist yet, the current defaults are returned.

## Updating settings

POST any subset of the parameters; omitted ones keep their current values. The endpoint creates the group if it doesn't exist yet, so you can configure a group before creating its first set.

```console
$ http POST $BASE/deduplication_set_groups/PROGRAM-2024-001/config/ \
    duplicate_confidence_threshold:=0.65 \
    sharpness_threshold:=0.3
```

The response echoes the full effective settings.

## Parameters

All values are floats in the **0–1** range.

| Parameter | Default | Effect |
|-----------|---------|--------|
| `face_detection_confidence_threshold` | 0.90 | Minimum detector confidence for a face to be accepted. Faces below it are reported with status **416**. |
| `duplicate_confidence_threshold` | 0.5 | Minimum match confidence for a pair to be reported as a duplicate. Higher = stricter matching (fewer false positives, more misses); lower = more permissive. |
| `sharpness_threshold` | 0 (disabled) | Minimum OFIQ sharpness score. |
| `dynamic_range_threshold` | 0 (disabled) | Minimum OFIQ dynamic range (contrast/exposure) score. |
| `no_head_cover_threshold` | 0 (disabled) | Minimum OFIQ no-head-coverings score. |
| `eyes_open_threshold` | 0 (disabled) | Minimum OFIQ eyes-open score. |
| `inter_eye_distance_threshold` | 0 (disabled) | Minimum OFIQ inter-eye distance (face resolution) score. |
| `unified_quality_score_threshold` | 0 (disabled) | Minimum OFIQ overall quality score. |

The six quality thresholds gate which images enter deduplication at all: an image failing any enabled threshold is excluded and reported with status **418**. Setting a threshold to `0` disables that check. See the [pipeline](../concepts/pipeline.md) for what each metric measures.

## Effects of changing settings

Settings changes are designed to keep results consistent:

- If the group has a set in `Encoded` or `Deduplicated` state, its **embeddings and findings are cleared** and the set moves back to `Ready`. Call `process` again to re-run with the new settings. (Cached image quality scores are kept, so re-runs are faster.)
- Every [finding](findings-and-statuses.md) carries a `config` snapshot of the settings it was produced with, so you can always tell which thresholds a result reflects.

## When changes are refused

The config endpoint returns **409 Conflict** when:

- a processing job is currently running in the group, or
- the group already contains an **approved** set — approved reference data was produced with specific settings, and changing them would make future comparisons inconsistent.

Plan your threshold tuning before the first approval: use `encode_only` runs and re-processing while the group has no approved sets.
