# Scripts for API interaction

## Requirements

These scripts use `httpie`, `jq`, and `mimetype` (Debian/Ubuntu package `libfile-mimeinfo-perl`), so make sure they are installed.

## Scripts

### Configuration

#### Internal

These scripts hold configuration and common functionality

| Name    | Arguments | Description                                     |
|---------|-----------|-------------------------------------------------|
| .vars   | -         | Contains configuration variables (base URL, token, current set id) |
| .common | -         | Contains common functions used by other scripts |

#### Public

| Name           | Arguments  | Description               |
|----------------|------------|---------------------------|
| use_base_url   | base url   | Sets base url             |
| use_auth_token | auth token | Sets authentication token |

### API interaction

| Name                      | Arguments                            | Description                                                              |
|---------------------------|--------------------------------------|--------------------------------------------------------------------------|
| create_deduplication_set  | reference_pk                         | Creates a new deduplication set and stores its id for following commands |
| create_image              | reference_pk, filename, [`--last`]   | Registers an image; with `--last` also calls the `ready` endpoint        |
| process_deduplication_set | -                                    | Starts processing and polls until the set state is `Deduplicated`        |
| show_deduplication_set    | -                                    | Shows deduplication set data (including state)                           |
| show_duplicates           | -                                    | Shows findings for the deduplication set                                 |
| approve                   | -                                    | Approves the deduplication set                                           |

### Test cases

| Name          | Arguments    | Description                                                                                                             |
|---------------|--------------|--------------------------------------------------------------------------------------------------------------------------|
| base_case     | reference pk | Creates a deduplication set, registers all demo images, runs processing, and shows duplicates                            |
| two_sets_case | reference pk | Runs and approves a first set, then processes a second set in the same group to demonstrate matching against approved data |
