# Demo Scripts

Shell scripts in `tests/extras/demoapp/biographic/` drive the biographic API end to end, the way HOPE would. They need [httpie](https://httpie.io/), [jq](https://jqlang.github.io/jq/) and `python3` (standard library only, for the fake data).

`full_flow` runs the whole scenario on a fresh program. A program's existing population is processed and approved first, then a new registration is deduplicated against it. The new registration contains planted cases, each a known variation of an existing person, and the script checks that every one of them comes out as expected.

## Running it

Start the stack as described in the [biometric demo](../../development/demo.md#running-the-demo-server) (`docker compose up --build`). Then create an API token under `Home › Api › Tokens` with the `API_BIOGRAPHIC` grant, or use a superuser's token.

```console
$ cd tests/extras/demoapp/biographic
$ ./use_base_url http://localhost:8000
$ ./use_auth_token <token>
$ ./full_flow                      # business area "afghanistan", a new program demo-<timestamp>
$ ./full_flow afghanistan my-demo  # or choose both
```

Each run uses a new program by default: a reused program already holds the people of earlier runs, and they would match the new ones.

## The scenario

```mermaid
flowchart TB
    gen["generate_people.py<br>400 people in households (population)<br>60 new people, 10 of them planted"]
    subgraph step1["Step 1: existing population"]
        c1[create dataset] --> u1["upload 400 records<br>4 calls of 100"] --> p1["process<br>poll until deduplicated"] --> s1["show findings<br>expected: none"] --> a1[approve]
    end
    subgraph step2["Step 2: new registration"]
        c2[create dataset] --> u2["upload 60 records<br>3 calls of 25"] --> p2["process<br>poll until deduplicated"] --> s2["show findings<br>all, then batch only"] --> k2["check_expected<br>PASS / FAIL per planted case"] --> a2[approve]
    end
    gen --> step1 --> step2
```

### The fake people

The population is made of households: a head, often a spouse, and up to three children, sharing a family name and the head's phone number. Every given and family name pair is unique, and no two names in the lists can be confused by spelling or sound, so the filler people never match each other. Every finding the API reports is therefore a planted one.

The new registration adds 50 unrelated people and these planted cases:

| New record | Population person | Variation | Expected | Score |
|------------|-------------------|-----------|----------|-------|
| `NEW-EXACT` | `POP-AMINA` | identical | duplicate | 14 |
| `NEW-SOUNDALIKE` | `POP-MARIAM` | Maryam / Mariam, same sound | duplicate | 14 |
| `NEW-TYPO` | `POP-RAHIM` | Rhaim / Rahim, a typo | duplicate | 13.2 |
| `NEW-NICKNAME` | `POP-JOHN` | Johnny / John, from the synonyms file | duplicate | 14 |
| `NEW-NOGIVEN` | `POP-NADIA` | given name missing, full name sent | duplicate | 14 |
| `NEW-NEWPHONE` | `POP-HAMID` | new phone, corrected birth date | duplicate | 10 |
| `NEW-NAMESAKE` | `POP-AHMAD` | same names, different birth date and phone | duplicate | 9 |
| `NEW-HOUSEHOLD` | `POP-HAMID` | his wife: same family name and phone | not a duplicate | about 3, below 6 |
| `NEW-BATCH-A` / `NEW-BATCH-B` | each other | the same person twice in the new registration | duplicate (`batch`) | 14 |

The namesake shows a property of the scoring rather than a bug: matching given and family names (8 points) clear the default threshold of 6 on their own, so namesakes need a human decision. See [Scoring Pipeline](../concepts/pipeline.md).

```mermaid
flowchart LR
    subgraph population["Approved population"]
        amina[POP-AMINA]
        hamid[POP-HAMID]
        ahmad[POP-AHMAD]
    end
    subgraph new["New registration"]
        exact[NEW-EXACT]
        newphone[NEW-NEWPHONE]
        household[NEW-HOUSEHOLD]
        namesake[NEW-NAMESAKE]
        batchA[NEW-BATCH-A]
        batchB[NEW-BATCH-B]
    end
    exact -- "population, 14" --> amina
    newphone -- "population, 10" --> hamid
    household -. "about 3: not reported" .-> hamid
    namesake -- "population, 9" --> ahmad
    batchA -- "batch, 14" --> batchB
    batchB -- "batch, 14" --> batchA
```

## What happens on each call

### Creating a dataset and uploading people

```mermaid
sequenceDiagram
    participant S as demo script
    participant API as HDE API
    participant DB as Postgres
    S->>API: POST /api/biographic/{ba}/{program}/datasets/
    API->>DB: register the program's group on first use, create the set (pending)
    API-->>S: 201 {dataset_id, status: pending}
    loop one call per batch (up to 10,000 records)
        S->>API: POST .../datasets/{id}/records/ {records: [...]}
        API->>DB: insert, or replace an existing reference_pk
        API-->>S: 201 {received, records_count}
    end
```

There is no endpoint for creating a group: the first dataset created for a business area and program registers it, with the default settings. Its thresholds can then be changed in the admin.

### Processing

```mermaid
sequenceDiagram
    participant S as demo script
    participant API as HDE API
    participant W as Celery worker
    participant ES as Elasticsearch
    S->>API: POST .../datasets/{id}/process/
    API->>W: queue the run
    API-->>S: 200 {status: indexing}
    W->>ES: index the set's people as pending
    W->>ES: search each person against the set and the approved population
    W->>W: store findings, status deduplicated
    loop every second until deduplicated (exit 1 on failed)
        S->>API: GET .../datasets/{id}/
        API-->>S: {status, records_count, batch_duplicates, population_duplicates}
    end
```

### Reading the findings and approving

```mermaid
sequenceDiagram
    participant S as demo script
    participant API as HDE API
    participant W as Celery worker
    participant ES as Elasticsearch
    S->>API: GET .../datasets/{id}/findings/?page_size=10000
    API-->>S: {count, results: [{reference_pk, matched_reference_pk, scope, score, proximity_to_score, ...}]}
    S->>S: check_expected compares them with expected.json
    S->>API: POST .../datasets/{id}/approve/
    API-->>S: 200 {status: approved}
    API->>W: queue the status update
    W->>ES: mark the set's documents approved
    Note over ES: later datasets in the program<br>are searched against these people
```

If the status update fails, the next run of the program applies it before searching, so the population is always complete.

### Dataset states seen by the scripts

```mermaid
stateDiagram-v2
    [*] --> pending: create_dataset
    pending --> indexing: process_dataset
    indexing --> deduplicating
    deduplicating --> deduplicated
    indexing --> failed
    deduplicating --> failed
    failed --> indexing: process_dataset again
    deduplicated --> approved: approve
    deduplicated --> rejected: reject
    pending --> canceled: cancel
    failed --> canceled: cancel
```

While a dataset is being processed or waits in `deduplicated`, the program's other datasets cannot be processed (409). This is why `full_flow` approves the population before processing the new registration.

## Scripts

State (base URL, token, program, current dataset) is kept in `.vars`, created on first use and ignored by git. Generated data goes to `data/`, also ignored.

| Script | Arguments | Description |
|--------|-----------|-------------|
| `use_base_url` | base url | Sets the API base URL |
| `use_auth_token` | token | Sets the API token |
| `use_program` | business area, program code | Selects the program for the following commands |
| `create_dataset` | `[notification_url]` | Creates a dataset and selects it |
| `upload_records` | file, `[batch_size]` (default 100) | Uploads a JSON list of `{reference_pk, payload}` in batches |
| `process_dataset` | `[overrides]`, e.g. `duplicate_score:=8` | Starts processing and polls until `deduplicated`; exits 1 on `failed` |
| `show_dataset` | – | Shows the dataset, with its state and duplicate counts |
| `show_findings` | `[--json] [filters]`, e.g. `scope==batch min_score==10 reference_pk==NEW-EXACT` | Lists the findings as a table, best first |
| `approve` / `reject` / `cancel` | – | Decides or abandons the dataset |
| `generate_people.py` | output dir, `[--population N] [--new N] [--seed N]` | Writes `population.json`, `new_registration.json` and `expected.json` |
| `check_expected` | `[expected.json]` | Compares the findings with the planted cases; exits 1 on any mismatch |
| `full_flow` | `[business_area] [program_code]` | Runs the whole scenario above |

Failed calls print the API's error and stop the script, for example `{"detail": "Cannot process set in 'Canceled' state."}`.
