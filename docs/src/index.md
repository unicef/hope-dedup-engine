# HOPE Deduplication Engine

The HOPE Deduplication Engine (HDE) is a service in the [HOPE](https://github.com/unicef/hope) ecosystem that finds duplicate individuals in a dataset by comparing their **facial photographs**. Client systems (for example HOPE Country Workspace) register a batch of images through a REST API, start processing, and read back a list of *findings* — pairs of records whose faces match with a similarity score above a configurable threshold.

Under the hood HDE uses [DeepFace](https://github.com/serengil/deepface) for face detection and recognition and [OFIQ](https://github.com/BSI-OFIQ/OFIQ-Project) for image quality assessment, with Celery workers doing the heavy lifting asynchronously.

## Where to go

The documentation is organized by audience:

| Section | For | Contents |
|---------|-----|----------|
| [Concepts](concepts/architecture.md) | Everyone | Architecture, the deduplication set lifecycle, data model, and the face recognition pipeline |
| [Integration Guide](integration/index.md) | Developers of client systems (e.g. Country Workspace) | Authentication, the end-to-end API workflow, configuration, findings, statuses, and notifications |
| [Administration](admin/deployment.md) | Operators and admins | Deployment, environment variables, admin panel settings, maintenance and troubleshooting |
| [Development](development/getting-started.md) | Contributors to HDE itself | Local setup, project layout, testing, the demo app, and contribution guidelines |

## Quick orientation

If you only read one page, read the [deduplication set lifecycle](concepts/lifecycle.md) — everything in the API revolves around it:

1. A client **creates a deduplication set** inside a *group* (identified by an external `reference_pk`, e.g. a HOPE program).
2. It **registers images** in one or more batches, then marks the set **ready**.
3. It triggers **processing**: faces are quality-checked, encoded into embeddings, and compared with each other — and with previously *approved* sets in the same group.
4. It reads the **findings** (duplicate pairs with similarity scores) and finally **approves** or **rejects** the results.

## Help

**Got a question?** File a GitHub [issue](https://github.com/unicef/hope-dedup-engine/issues).
