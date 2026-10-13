# Environment Variables

Biographic deduplication adds three variables to the [main environment reference](../../admin/environment.md). All are optional at startup; `ELASTICSEARCH_HOST` is needed as soon as a biographic run starts.

| Variable | Default | Description |
|----------|---------|-------------|
| `ELASTICSEARCH_HOST` | *(empty)* | URL of the biographic Elasticsearch cluster, e.g. `http://elasticsearch:9200`. Empty means biographic runs fail with "ELASTICSEARCH_HOST is not set". The development default is `http://localhost:9200`. |
| `ELASTICSEARCH_PREFIX` | *(empty)* | Prepended to every biographic index name so several environments can share one cluster, e.g. `staging_` gives `staging_biographic_afg_prog-2026`. The daily cleanup only touches indices with this deployment's prefix. |
| `ELASTICSEARCH_SYNONYMS_FILE` | *(empty)* | Path to the nickname synonyms file (one comma-separated group per line, e.g. `william,bill,billy`). Empty uses the copy bundled in the `biographic` app. |

!!! note "Synonyms are fixed per index"
    The synonyms are written into an index's settings when it is created. Changing the file affects only programs whose index is created afterwards, and it changes their scores: keep it identical to HOPE's to stay comparable.

Requests to the cluster time out after 30 seconds.

The variables also appear in the auto-generated [Settings reference](../../settings.md).
