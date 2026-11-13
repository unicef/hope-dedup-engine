# Application Settings

Like the biometric settings, biographic thresholds live on two levels: **global defaults** and **per-program settings**.

## Global defaults (Constance)

    Home › Constance › Config › Biographic deduplication settings

| Key | Default | Description |
|-----|---------|-------------|
| `DEFAULT_BIOGRAPHIC_DUPLICATE_SCORE` | `6.0` | Pairs scoring at or above this are duplicates; also the Elasticsearch `min_score`. HOPE's default. |
| `DEFAULT_BIOGRAPHIC_MAX_HITS` | `100` | Maximum matches returned per person. |

These are the defaults for **new programs**: a program snapshots them when its first set is created, so changing a default does not affect existing programs. A setting added to the engine later is read from Constance by programs whose snapshot doesn't have it yet.

## Per-program settings

    Home › Biographic › Biographic groups › <business area:program>

The change form has a *Deduplication settings* section with one field per setting, validated with the same minimums as the API (`duplicate_score` ≥ 0, `max_hits` ≥ 1). Business area, program code, lock and deleted flag are read-only; programs cannot be added by hand.

Unlike biometric settings, a change is **never refused**: a run reads the settings once when it starts and every finding keeps the snapshot it was scored with, so the change applies from the next run, and nothing is cleared. Clients can still override either value for a single run. See [Configuration](../integration/configuration.md#where-the-values-come-from).

## Permissions

| Permission | Allows |
|------------|--------|
| `biographic | biographic group | Can release processing lock` | The *Unlock processing* and *Mark as failed* buttons on a set. |
| `biographic | biographic set | Can send notification` | The *Send notification* button on a set. |
| `biographic | biographic set | Can index records` | The *Index records* button on a set. |
| `biographic | biographic set | Can find duplicates` | The *Find duplicates* button on a set. |
| `biographic | biographic group | Can rebuild index` | The *Rebuild index* button on a group and on a set. |
| `biographic | biographic group | Can change biographic group` | Editing a program's settings. |

API access is not a Django permission: it is the **Api Biographic** grant on the client's token (see [Deployment](deployment.md#creating-api-credentials)).
