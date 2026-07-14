# Notifications and Polling

Processing is asynchronous — after `POST .../process/` returns `{"message": "started"}`, the work happens in a background worker. There are two ways to track it.

## Polling

`GET /deduplication_sets/{id}/` returns the current `state`. Poll until it reaches a terminal state for the operation you started:

- full run: `Deduplicated` (success), `Encoding failed` or `Deduplication failed` (failure)
- `encode_only` run: `Encoded` (success), `Encoding failed` (failure)

Processing time depends on the number of images, the enabled quality checks, and worker capacity — expect seconds for small sets and use generous timeouts for large ones.

## Webhook notifications

If you set a `notification_url` when [creating the set](workflow.md#1-create-a-deduplication-set), the engine sends a request to that URL at every state transition during processing:

- when the job starts (`Encoding in progress`)
- after encoding completes (`Encoded`)
- when deduplication starts (`Deduplication in progress`)
- when deduplication completes (`Deduplicated`)
- on failure (`Encoding failed` / `Deduplication failed`)

The notification is a plain **HTTP GET** to your URL, with **no payload** — it's a nudge, not a data delivery. On receiving it, call `GET /deduplication_sets/{id}/` to learn the new state. Encode any correlation data you need (e.g. your own set identifier) into the URL itself as query parameters.

If the engine is configured with a HOPE API token, the callback carries an `Authorization: Token <token>` header your endpoint can use to authenticate the caller.

Details worth knowing:

- Notifications can be disabled per set by creating it with `"notify": false`; the `notification_url` is kept, so administrators can still trigger a manual notification from the admin panel.
- The callback has a 5-second timeout. Failures to deliver are logged to Sentry but **do not** affect processing — the set continues through its lifecycle regardless.
- Delivery is not retried; treat webhooks as an optimization and keep a polling fallback for reliability.

## Error handling summary

| Signal | Where | Meaning |
|--------|-------|---------|
| `state: "Encoding failed"` / `"Deduplication failed"` | set detail | The run aborted with an unexpected error. The `error` details are available to administrators; retry with `POST .../process/`. |
| Findings with `status_code` ≠ 200 | findings list | Individual images that could not be used — the run itself succeeded. See [status codes](findings-and-statuses.md#image-status-codes). |
| HTTP 409 on any call | API response | Operation not allowed in the current [lifecycle state](../concepts/lifecycle.md), or another job/active set blocks it. The response body explains which. |
