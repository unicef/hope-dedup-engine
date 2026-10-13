# Biographic Deduplication

Biographic deduplication finds duplicate individuals by comparing **what is known about them** — names, birth date, phone numbers, sex, relationship — rather than their photographs. A client system (for example HOPE Country Workspace) uploads a set of people for one business area and program, starts processing, and reads back *pairs*: people who score above a threshold against someone else in the same set or in the program's already-approved population.

Scoring is a port of HOPE's own Elasticsearch deduplication (`DeduplicateTask`): the same index settings, analyzers, similarity script, query and default threshold, so a score here means what it means in HOPE. It runs on a **dedicated Elasticsearch cluster**, separate from HOPE's.

It lives in the `biographic` app and is independent of the [biometric (face) deduplication](../index.md): its own API under `/api/biographic/`, its own token grant, models, admin pages and Celery tasks. The two share only the notification helper and the deployment.

## Where to go

| Section | For | Contents |
|---------|-----|----------|
| [Concepts](concepts/architecture.md) | Everyone | Architecture, the set lifecycle, data model, how a score is computed, and [sequence diagrams](concepts/sequence-diagrams.md) of every flow |
| [Integration Guide](integration/index.md) | Developers of client systems | Authentication, the end-to-end API workflow, configuration, pairs and statuses, notifications |
| [Administration](admin/deployment.md) | Operators and admins | The Elasticsearch cluster, environment variables, settings, maintenance and troubleshooting |
| [Development](development/project-structure.md) | Contributors | Code layout, conventions, and how to test against a real or fake Elasticsearch |

## Quick orientation

Everything revolves around the [set lifecycle](concepts/lifecycle.md):

1. A client **creates a set** for a business area and program (`/api/biographic/{business_area}/{program_code}/datasets/`). The program is registered on first use.
2. It **uploads people** in batches of up to 10,000 records.
3. It triggers **processing**: the set is indexed into the program's Elasticsearch index and every person is scored against the rest of the set and against the program's *approved* population.
4. It reads the **pairs**, then **approves** the set (its people join the population that later sets are checked against) or **rejects** it.

Only one set per program can be processed or awaiting a decision at a time; any number can be created and filled while it waits.
