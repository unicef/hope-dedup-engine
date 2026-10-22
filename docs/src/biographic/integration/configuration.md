# Configuration

Two settings control a run. Each program stores its own values; a client can override them for one run.

## Parameters

| Parameter | Default | Effect |
|-----------|---------|--------|
| `duplicate_score` | 6.0 | Pairs scoring at or above this are duplicates. It is also the Elasticsearch `min_score`, so nothing below it is ever returned or stored. Higher means stricter. HOPE's default. Minimum 0. |
| `max_hits` | 100 | Maximum matches returned per person, best first. A person who reaches it is counted as *truncated* in the run log. Minimum 1. |

See the [scoring pipeline](../concepts/pipeline.md) for what a score is made of, and why matching given and family names alone already reaches 6.0.

!!! note "No abort thresholds"
    HOPE also aborts a run when too many records have duplicates. That rule is deliberately not implemented here: a run always ends `deduplicated`, and the client decides what `batch_duplicates` and `population_duplicates` mean.

## Where the values come from

For each run, every setting is resolved in this order:

1. the **override** sent in the body of `POST .../process/`,
2. the **program's settings**, snapshotted from the global defaults when the program was registered and editable by an administrator ([admin settings](../admin/settings.md#per-program-settings)),
3. the **global default** (Constance), for a setting added after the program was registered.

## Overriding for one run

```console
$ http POST $P/datasets/17/process/ duplicate_score:=8.0
```

- Any subset of the parameters; the others come from the program.
- An unknown key is a **400** (`"Unknown setting."`), as is a value below the minimum.
- Overrides are stored on the run's job and in the run log, and apply to that run only.

There is no client endpoint to change or read a program's stored settings; they are administered in the admin panel.

## Effects of changing settings

A run reads its settings once, when it starts. Changing a program's settings or the global defaults therefore:

- never touches a run in progress or results already stored,
- applies from the next run,
- is never refused, unlike biometric settings: there is nothing derived from the settings to clear.

Every finding stores the settings it was scored with, and `proximity_to_score` is relative to the threshold of its own run, so results from different runs stay comparable.
