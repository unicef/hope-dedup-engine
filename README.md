ABOUT HOPE Deduplication Engine
===============================

[![Test](https://github.com/unicef/hope-dedup-engine/actions/workflows/test.yml/badge.svg)](https://github.com/unicef/hope-dedup-engine/actions/workflows/test.yml)
[![Lint](https://github.com/unicef/hope-dedup-engine/actions/workflows/lint.yml/badge.svg)](https://github.com/unicef/hope-dedup-engine/actions/workflows/lint.yml)
[![codecov](https://codecov.io/gh/unicef/hope-dedup-engine/graph/badge.svg?token=kAuZEX5k5o)](https://codecov.io/gh/unicef/hope-dedup-engine)
![Version](https://img.shields.io/badge/dynamic/toml?url=https%3A%2F%2Fraw.githubusercontent.com%unicef%2Fhope-dedup-engine%2Fdevelop%2Fpyproject.toml&query=%24.project.version&label=version)
![License](https://img.shields.io/badge/dynamic/toml?url=https%3A%2F%2Fraw.githubusercontent.com%2Funicef%2Fhope-dedup-engine%2Fdevelop%2Fpyproject.toml&query=%24.project.license.text&label=license)


## Configuration and Usage

#### Display the Current Configuration

    $ docker run -it -t  unicef/hope-dedupe-engine:release-0.1 django-admin env
    
#### Check Mandatory Environment Variables

    $ docker run -it -t  unicef/hope-dedupe-engine:release-0.1 django-admin env --check

Ensure the following environment variables are properly configured:

- **DATABASE_URL**: The URL for the database connection.
  *Example:* `postgres://hde:password@db:5432/hope_dedupe_engine`

- **SECRET_KEY**: A secret key for the Django installation.
  *Example:* `django-insecure-pretty-strong`

- **CACHE_URL**: The URL for the cache server.
  *Example:* `redis://redis:6379/1`

- **CELERY_BROKER_URL**: The URL for the Celery broker.
  *Example:* `redis://redis:6379/9`

- **DEFAULT_ROOT**: The root directory for locally stored files.
  *Example:* `/var/hope_dedupe_engine/default`

- **MEDIA_ROOT**: The root directory for media files.
  *Example:* `/var/hope_dedupe_engine/media`

- **STATIC_ROOT**: The root directory for static files.
  *Example:* `/var/hope_dedupe_engine/static`

#### Storage Configuration
The service uses the following storage backends:
- **FILE_STORAGE_DEFAULT**: This backend is used for storing locally downloaded DNN model files and encoded data.
    ```
    FILE_STORAGE_DEFAULT=django.core.files.storage.FileSystemStorage
    ```
- **FILE_STORAGE_DNN**:
This backend is dedicated to storing DNN model files. Ensure that the following two files are present in this storage and that they have exactly these names:
    1. *deploy.prototxt*: Defines the model architecture. Download it from the [model architecture link](https://raw.githubusercontent.com/sr6033/face-detection-with-OpenCV-and-DNN/master/deploy.prototxt.txt)
    2. *res10_300x300_ssd_iter_140000.caffemodel*: Contains the pre-trained model weights. Download it from the [model weights link](https://raw.githubusercontent.com/sr6033/face-detection-with-OpenCV-and-DNN/master/res10_300x300_ssd_iter_140000.caffemodel)

    These files can be updated in the future by a dedicated pipeline that handles model training. The storage configuration for this backend is as follows:
    ```
    FILE_STORAGE_DNN="storages.backends.azure_storage.AzureStorage?account_name=<account_name>&account_key=<account_key>&overwrite_files=true&azure_container=dnn"
    ```

- **FILE_STORAGE_HOPE**: This backend is used for storing HOPE dataset images. It should be configured as read-only for the service.
    ```
    FILE_STORAGE_HOPE="storages.backends.azure_storage.AzureStorage?account_name=<account_name>&account_key=<account_key>&azure_container=hope"
    ```
- **FILE_STORAGE_MEDIA**: This backend is used for storing media files.

- **FILE_STORAGE_STATIC**: This backend is used for storing static files, such as CSS, JavaScript, and images.

#### To run server and support services

    $ docker run -d -t  unicef/hope-dedupe-engine:release-0.1
    $ docker run -d -t  unicef/hope-dedupe-engine:release-0.1 worker
    $ docker run -d -t  unicef/hope-dedupe-engine:release-0.1 beat
    
## Demo application

#### To run locally demo server with the provided sample data

    $ docker compose -f tests/extras/demoapp/compose.yml up --build

You can access the demo server admin panel at http://localhost:8000/admin/ with the following credentials: `adm@hde.org`/`123`

#### API documentation and interaction
API documentation is available at [Swagger UI](http://localhost:8000/api/rest/swagger/) and [Redoc](http://localhost:8000/api/rest/redoc/)

Scripts for API interaction are located in the `tests/extras/demoapp/scripts` directory. These scripts require `httpie` and `jq` to be installed.

For more information, refer to the  [demoapp README](tests/extras/demoapp/scripts/README.md)

## Development

To develop the service locally, use the provided `compose.yml` file. This will start the service and all necessary dependencies.

    $ docker compose up --build

To run the tests, use:
    
    $ docker compose run --rm backend pytest tests -v --create-db

After running the tests, you can view the coverage report at the `~build/coverage` directory.


## Help
**Got a question?** We got answers.

File a GitHub [issue](https://github.com/unicef/hope-dedup-engine/issues)
