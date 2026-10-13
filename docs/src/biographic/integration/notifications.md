# Notifications and Polling

After `POST .../process/` returns, the run happens in a background worker. There are two ways to follow it.

## Polling

`GET .../datasets/{id}/` returns the current `status`. Poll until it is:

- `deduplicated` — success; read the pairs.
- `failed` — the run stopped; `error` says why. Call `process` to retry, or `cancel`.

A run indexes and scores in chunks, so its time grows linearly with the set: in testing, a set of about 4,500 people took about 10 seconds against a local cluster. Use generous timeouts for large sets.

## Webhook notifications

If the set was created with a `notification_url`, the worker sends a request to it at every state change **a run makes**:

- when the run starts (`indexing`)
- after indexing (`indexed`)
- when scoring starts (`deduplicating`)
- when the run completes (`deduplicated`)
- on failure or cancellation (`failed`)

Approve, reject and cancel are your own calls and are not notified.

The notification is a plain **HTTP GET** with **no payload and no credentials**. On receiving it, call `GET .../datasets/{id}/` for the new state. Put any correlation data you need into the URL as query parameters.

Details worth knowing:

- `notify: false` at creation turns notifications off; the URL is kept, so an administrator can still send one from the admin panel.
- Each request has a 5-second timeout and is retried up to 3 times on a connection error or a 429, 500, 502, 503 or 504 response. Other 4xx responses are not retried.
- A failed delivery never affects the run. It is reported to Sentry, and the outcome of every notification (`sent`, or the error) is recorded in the set's run log.
- Keep polling as a fallback: notifications are a nudge, not a guarantee.

## Error handling summary

| Signal | Where | Meaning |
|--------|-------|---------|
| `status: "failed"` | set detail | The run stopped with an unexpected error or was cancelled by an administrator. `error` holds the reason; retry with `POST .../process/`. |
| `population_duplicates` / `batch_duplicates` high | set detail | Not an error. The run never aborts on duplicate counts; decide from the pairs. |
| HTTP 409 on any call | API response | Not allowed in the current [state](../concepts/lifecycle.md), or another set or run in the program blocks it. The `detail` explains which. |
