# Demo App and API Scripts

A self-contained demo environment with sample images and helper scripts lets you exercise the whole system — including the REST API — without configuring anything.

## Running the demo server

```console
$ docker compose -f tests/extras/demoapp/compose.yml up --build
```

(The root `compose.yml` also seeds the same demo data via the `demo` management command.)

Admin panel access:

- URL: [http://localhost:8000/admin](http://localhost:8000/admin)
- Username: `adm@hde.org`
- Password: `123`

The demo setup creates an external system and an API token you can find under `Home › Api › Tokens`.

## API interaction scripts

Shell scripts in `tests/extras/demoapp/scripts/` drive the API end to end. They require [httpie](https://httpie.io/) and [jq](https://jqlang.github.io/jq/).

### Configuration

State (base URL, token, current set id) is kept in `.vars` and shared helpers in `.common`.

| Script | Arguments | Description |
|--------|-----------|-------------|
| `use_base_url` | base url | Sets the API base URL |
| `use_auth_token` | auth token | Sets the authentication token |

### API interaction

| Script | Arguments | Description |
|--------|-----------|-------------|
| `create_deduplication_set` | reference_pk | Creates a deduplication set (stores its id for the following commands) |
| `create_image` | reference_pk, filename, [`--last`] | Registers an image; with `--last` also calls the `ready` endpoint |
| `process_deduplication_set` | – | Starts processing and polls until the set reaches `Deduplicated` |
| `show_deduplication_set` | – | Shows the set (including its state) |
| `show_duplicates` | – | Lists the findings |
| `approve` | – | Approves the set |

### End-to-end cases

| Script | Arguments | Description |
|--------|-----------|-------------|
| `base_case` | reference pk | Creates a set, registers all demo images, processes, and shows duplicates |
| `two_sets_case` | reference pk | Full group scenario: first set processed and **approved**, then a second set in the same group is processed — demonstrating matching against approved reference data |

Typical session:

```console
$ cd tests/extras/demoapp/scripts
$ ./use_base_url http://localhost:8000
$ ./use_auth_token <token-from-admin>
$ ./base_case DEMO-PROGRAM-1
```
