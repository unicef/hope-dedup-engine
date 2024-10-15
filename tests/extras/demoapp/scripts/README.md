# Scripts for API interaction

## Requirements

These scripts use `httpie` and `jq`, so make sure they are installed.

## Scripts

### Configuration

#### Internal

These scripts hold configuration and common functionality

| Name                  | Arguments | Description                                     |
|-----------------------|-----------|-------------------------------------------------|
| .vars                 | -         | Contains configuration variables                |
| .common               | -         | Contains common functions used by other scripts |

#### Public

| Name                  | Arguments            | Description               |
|-----------------------|----------------------|---------------------------|
| use_base_url          | base url             | Sets base url             |
| use_auth_token        | auth token           | Sets authentication token |
| use_deduplication_set | deduplication set id | Sets deduplication set id |

### API interaction

| Name                      | Arguments                               | Description                                 |
|---------------------------|-----------------------------------------|---------------------------------------------|
| create_deduplication_set  | reference_pk                            | Creates new deduplication set               |
| create_image              | filename                                | Creates image in deduplication set          |
| ignore                    | first reference pk, second reference pk | Makes API ignore specific reference pk pair |
| process_deduplication_set | -                                       | Starts deduplication process                |
| show_deduplication_set    | -                                       | Shows deduplication set data                |
| show_duplicates           | -                                       | Shows duplicates found in deduplication set |

### Test cases

| Name             | Arguments    | Description                                                                                                                    |
|------------------|--------------|--------------------------------------------------------------------------------------------------------------------------------|
| base_case        | reference pk | Creates deduplication set, adds images to it and runs deduplication process                                                    |
| all_ignored_case | reference pk | Creates deduplication set, adds images to it, adds all possible reference pk pairs to ignored pairs and shows duplicates found |
