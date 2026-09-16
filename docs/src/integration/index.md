# Integrating with the Deduplication Engine

This guide is for developers of client systems — such as HOPE Country Workspace — that use the engine's REST API to deduplicate a set of individuals by their photographs.

Before you start, make sure you understand the [deduplication set lifecycle](../concepts/lifecycle.md): almost every API error you will encounter is a 409 telling you an operation is not allowed in the set's current state.

## API reference

The complete, always-up-to-date endpoint reference is generated from the code and served by the application itself:

- **Swagger UI** (interactive): `https://<server>/api/rest/swagger/`
- **Redoc** (reference): `https://<server>/api/rest/redoc/`
- **OpenAPI schema** (machine-readable): `https://<server>/api/rest/`

This guide focuses on the workflow and semantics that the schema alone doesn't convey.

## Authentication

Every request must carry a token:

```
Authorization: Token <your-token>
```

Tokens are issued by an engine administrator through the admin panel (see [admin guide](../admin/deployment.md#creating-api-credentials)). A token is bound to a user *and* an external **System**; all data you create and read is scoped to that system — you can never see another system's groups or sets.

If your token is missing or invalid you get **401**; if the user lacks the API permission you get **403**.

## Core resources

| Resource | Endpoint | Purpose |
|----------|----------|---------|
| Deduplication sets | `/deduplication_sets/` | Create, list, retrieve, delete sets; trigger `process`, `ready`, `approve`, `reject` |
| Images | `/deduplication_sets/{id}/images/` | Register image batches; `clear` to start over |
| Findings | `/deduplication_sets/{id}/findings/` | Read results (paginated, filterable) |
| Group config | `/deduplication_set_groups/{reference_pk}/config/` | Read / update per-group thresholds |
| Group status | `/deduplication_set_groups/{reference_pk}/status/` | Check whether a new set can be created |

Two identifiers appear throughout and are **yours to choose**:

- **Group `reference_pk`** — identifies the group of related deduplication runs, e.g. your program/project ID. Sets created with the same `reference_pk` belong to the same group and share settings and approved reference data.
- **Image `reference_pk`** — identifies the individual/record an image belongs to, e.g. your individual ID. Findings refer to images by this value.

## Images

You register images by providing a `reference_pk` (your identifier for the individual) and a `filename` — the path/key of the image in the shared HOPE blob storage (`FILE_STORAGE_HOPE`). The engine reads the image directly from that storage during processing; it doesn't receive or store the image bytes itself. If the file cannot be found at processing time, that image is reported in the findings with status code **404**.

## Where to next

- [End-to-end workflow](workflow.md) — the full request sequence with examples.
- [Configuration](configuration.md) — tuning thresholds per group.
- [Findings and statuses](findings-and-statuses.md) — interpreting results.
- [Notifications and polling](notifications.md) — tracking progress.
