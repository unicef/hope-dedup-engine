# Integrating with Biographic Deduplication

This guide is for developers of client systems — such as HOPE Country Workspace — that deduplicate individuals by their biographic data through the engine's REST API.

Read the [set lifecycle](../concepts/lifecycle.md) first: most API errors are a 409 saying an operation is not allowed in the set's current state, or that another set in the program is in the way.

## API reference

The endpoint reference is generated from the code and served by the application:

- **Swagger UI**: `https://<server>/api/rest/swagger/`
- **Redoc**: `https://<server>/api/rest/redoc/`
- **OpenAPI schema**: `https://<server>/api/rest/`

This guide covers the workflow and the semantics the schema doesn't convey.

## Authentication

Every request carries a token:

```
Authorization: Token <your-token>
```

Biographic endpoints use `hope_api_auth` API tokens, not the system-scoped tokens of the biometric API. An administrator creates the token with the **API Biographic** grant (see [Deployment](../admin/deployment.md#creating-api-credentials)). A token can be limited to a validity window (`valid_from` / `valid_to`).

| Response | Meaning |
|----------|---------|
| 401 | Missing or unknown token, a token outside its validity window, or an inactive user. |
| 403 | The token is valid but has no `API_BIOGRAPHIC` grant. |

!!! warning "A grant covers every program"
    The grant is not scoped to a business area or program: a token with `API_BIOGRAPHIC` can reach every program on the server. Issue tokens to trusted systems only.

## Addressing a program

Every route starts with the business area and program:

```
/api/biographic/{business_area_slug}/{program_code}/
```

Both are lowercased by the server, so `AFG` and `afg` are the same program. The program is registered the first time a set is created for it; there is nothing to set up beforehand. A set id used under the wrong program returns 404.

## Core resources

| Resource | Endpoint | Purpose |
|----------|----------|---------|
| Sets | `.../datasets/` | Create a set (`POST`), read it (`GET .../datasets/{id}/`) |
| Records | `.../datasets/{id}/records/` | Upload a batch of people |
| Actions | `.../datasets/{id}/process/`, `cancel/`, `approve/`, `reject/` | Move the set through its lifecycle |
| Findings | `.../datasets/{id}/findings/` | Read the duplicate findings (paginated, filterable) |

There is no list or delete endpoint for sets: a client keeps the `dataset_id` it was given, and abandons a set with `cancel`.

Two identifiers are yours to choose:

- **Business area and program code** — the isolation unit. People are only ever compared within one program.
- **Record `reference_pk`** — your identifier for the individual, e.g. a Country Workspace individual id. Findings refer to people by this value. Do not reuse one `reference_pk` for two different people: a person is never matched against documents carrying their own `reference_pk`.

## Where to next

- [End-to-end workflow](workflow.md) — the full request sequence with examples.
- [Configuration](configuration.md) — the thresholds and per-run overrides.
- [Findings and statuses](findings-and-statuses.md) — reading the results.
- [Notifications and polling](notifications.md) — tracking a run.
