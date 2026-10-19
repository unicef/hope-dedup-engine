# Findings and Statuses

Findings are the output of a run. They are available from

```
GET /api/biographic/{business_area}/{program_code}/datasets/{id}/findings/
```

once the set is `deduplicated`, and stay available after it is `approved`. In any other state the endpoint returns **409**.

## Response format

```json
{
    "count": 1211,
    "next": "https://.../findings/?page=2",
    "previous": null,
    "results": [
        {
            "reference_pk": "IND-0001",
            "matched_reference_pk": "IND-0937",
            "scope": "batch",
            "score": 12.0,
            "proximity_to_score": 6.0,
            "matched_full_name": "Amina Yusuf",
            "matched_birth_date": "1990-04-12"
        },
        {
            "reference_pk": "IND-0002",
            "matched_reference_pk": "IND-7781",
            "scope": "population",
            "score": 8.0,
            "proximity_to_score": 2.0,
            "matched_full_name": "Omar Yusuf",
            "matched_birth_date": null
        }
    ]
}
```

| Field | Meaning |
|-------|---------|
| `reference_pk` | The person in this set. |
| `matched_reference_pk` | The person they matched. |
| `scope` | `batch`: the match is in the same set. `population`: the match is an approved person of the program, from an earlier set. |
| `score` | Elasticsearch score with HOPE's scoring. Not bounded to 0–1; see the [pipeline](../concepts/pipeline.md). |
| `proximity_to_score` | `score` minus the `duplicate_score` used for this run. Always ≥ 0. |
| `matched_full_name`, `matched_birth_date` | The matched person's name and birth date as indexed, so a reviewer can see the match without another lookup. |

**Findings are directional.** When two people in the same set match each other, the match is listed once from each side (A → B and B → A), as HOPE reports it per individual. Population findings are listed only from the side of the new set.

A person can have several findings. If a matched person appears in more than one approved set, only the best-scoring match is listed.

## Set status fields

`GET .../datasets/{id}/` returns the set with:

| Field | Meaning |
|-------|---------|
| `status` | The [lifecycle state](../concepts/lifecycle.md#states). |
| `error` | Why the last run failed, when `status` is `failed`. |
| `records_count` | Records uploaded. |
| `batch_duplicates` | Records with at least one `batch` finding. |
| `population_duplicates` | Records with at least one `population` finding. |

## Pagination and filtering

Results are paginated with `page` / `page_size` (default 1000, maximum 10000) and ordered best score first. Filters:

| Query parameter | Example | Effect |
|-----------------|---------|--------|
| `scope` | `?scope=population` | Only findings within the set (`batch`) or against the population. |
| `min_score` | `?min_score=10` | Only findings scoring at least this. |
| `reference_pk` | `?reference_pk=IND-0001` | Only the findings of one person of the set. |

```console
$ http GET "$P/datasets/17/findings/?scope=batch"                # duplicates inside the batch
$ http GET "$P/datasets/17/findings/?scope=population&min_score=10"  # strong matches to approved people
```

## Error responses

| Code | When |
|------|------|
| 400 | Invalid body: a payload field of the wrong type, an invalid date, the same `reference_pk` twice in a batch, more than 10,000 records, an unknown or out-of-range setting. The body names the offending fields. |
| 401 / 403 | See [authentication](index.md#authentication). |
| 404 | No such set in this program. |
| 409 | The operation is not allowed in the set's state, another set in the program is active, a run is already in progress, the set has no records, or the program was deleted. The `detail` explains which. |
