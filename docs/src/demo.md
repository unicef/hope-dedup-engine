To help you explore the functionality of this project, a demo server can be run locally using the provided sample data. This demo server includes pre-configured settings and sample records to allow for a comprehensive overview of the application's features without needing to configure everything from scratch.


## Running the Demo Server Locally

To set up and start the demo server locally, use the following command:
    
    docker compose -f tests/extras/demoapp/compose.yml up --build

This command will build and launch all necessary containers for the demo environment, allowing you to see how different components of the system interact. Once everything is running, you can access the demo server's admin panel to manage and configure various settings within the application.

## Accessing the Admin Panel

The admin panel is accessible via the following URL in your browser, using the credentials below:

- URL: **http://localhost:8000/admin**
- Username: **adm@hde.org**
- Password: **123**


## API Interaction

To further understand how the API works and how different endpoints can be used, there are scripts available for API interaction. These scripts are located in the `tests/extras/demoapp/scripts` directory.

### Prerequisites

To use these scripts, ensure that the following tools are installed:

- [httpie](https://httpie.io/): A command-line HTTP client, used for making API requests in a more readable format compared to traditional curl.
- [jq](https://jqlang.github.io/jq/) : A lightweight and flexible command-line JSON processor that allows you to parse and manipulate JSON responses from API endpoints.

### Scripts Overview

#### Configuration Scripts

Configuration scripts are used to set up the environment for the API interactions. These scripts hold internal settings and functions that are shared across multiple API interaction scripts, making it easier to reuse common functionality and standardize configuration.

| Name                  | Arguments | Description                                     |
|-----------------------|-----------|-------------------------------------------------|
| .vars                 | -         | Contains configuration variables                |
| .common               | -         | Contains common functions used by other scripts |


#### Public Scripts

These scripts help manage specific parameters for API interactions, allowing for easy setup and modification of variables that will be used in other commands.

| Name                  | Arguments            | Description               |
|-----------------------|----------------------|---------------------------|
| use_base_url          | base url             | Sets base url             |
| use_auth_token        | auth token           | Sets authentication token |
| use_deduplication_set | deduplication set id | Sets deduplication set id |


#### API Interaction Scripts

These scripts are used to interact directly with the API endpoints, performing various operations like creating deduplication sets, uploading images, starting the deduplication process, and retrieving results.

| Name                      | Arguments                               | Description                                 |
|---------------------------|-----------------------------------------|---------------------------------------------|
| create_deduplication_set  | reference_pk                            | Creates new deduplication set               |
| create_image              | filename                                | Creates image in deduplication set          |
| ignore                    | first reference pk, second reference pk | Makes API ignore specific reference pk pair |
| process_deduplication_set | -                                       | Starts deduplication process                |
| show_deduplication_set    | -                                       | Shows deduplication set data                |
| show_duplicates           | -                                       | Shows duplicates found in deduplication set |


#### Test Case Scripts

Test case scripts are designed to automate end-to-end testing scenarios, making it easy to validate the deduplication functionality.

| Name             | Arguments    | Description                                                                                                                    |
|------------------|--------------|--------------------------------------------------------------------------------------------------------------------------------|
| base_case        | reference pk | Creates deduplication set, adds images to it and runs deduplication process                                                    |
| all_ignored_case | reference pk | Creates deduplication set, adds images to it, adds all possible reference pk pairs to ignored pairs and shows duplicates found |