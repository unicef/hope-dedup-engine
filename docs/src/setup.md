---
tags:
  - Deduplication
---

## Prerequisites

This project utilizes [UV](https://docs.astral.sh/uv/) as the package manager for managing Python dependencies and environments. 

To successfully set up and run this project, ensure that you have the following components in place:

- **Postgres Database (v14+)**: A PostgreSQL database instance is required to store application data. Ensure that version 14 or newer is available and accessible.
- **Redis Server**: Redis is used for caching and managing task queues. Ensure you have a running Redis server.
- **Celery Worker(s)**: Celery is used for handling asynchronous tasks in the application. One or more workers are needed to process these tasks.
- **Celery Beat**: Celery Beat is used for scheduling periodic tasks. Ensure that Celery Beat is configured and running.
- **Azure Blob Storage Account(s)**: Azure Blob Storage is utilized for storing application files and media. Make sure you have access to one or more Azure Blob Storage accounts for file management.

The code for this project is encapsulated within a Docker image, which provides an isolated and consistent environment for running the application. This Docker image is hosted on [Docker Hub](https://hub.docker.com/r/unicef/hope-dedupe-engine/), allowing easy access and deployment.

## Environment Configuration

Essential steps for verifying and configuring the environment settings required to run the project are provided. Instructions include displaying the current configuration, checking for missing variables, and ensuring all required settings are properly defined. Detailed descriptions of each variable are also available.

### Display the Current Configuration

    $ docker run -it -t  unicef/hope-dedupe-engine:release-0.x django-admin env

### Mandatory Environment Variables
Check Environment Variables

    $ docker run -it -t  unicef/hope-dedupe-engine:release-0.x django-admin env --check

Ensure the following environment variables are properly configured:
    
    ADMIN_EMAIL
    ADMIN_PASSWORD
    ALLOWED_HOSTS
    CACHE_URL
    CELERY_BROKER_URL
    CSRF_COOKIE_SECURE
    DATABASE_URL
    DEEPFACE_HOME
    FILE_STORAGE_HOPE
    FILE_STORAGE_STATIC
    FILE_STORAGE_MEDIA
    MEDIA_ROOT
    SECRET_KEY
    STATIC_ROOT

### Variables Breakdown

Detailed information about the required environment variables is provided for clarity and proper configuration.

#### Operational

##### ADMIN_EMAIL
The email address for the admin user that can access the Django admin panel with full privileges. *Example:* `adm@myhost.org`

##### ALLOWED_HOSTS
A list of host/domain names that the application can serve. *Example:* `['*']`

##### ADMIN_PASSWORD
The password for the admin user. *Example:* `123`

##### CACHE_URL
The URL for the cache server. *Example:* `redis://redis:6379/1`

##### CELERY_BROKER_URL
The URL for the Celery broker. *Example:* `redis://redis:6379/9`

##### CSRF_COOKIE_SECURE
A boolean value that determines whether the CSRF cookie should be secure. *Example:* `False`

##### DATABASE_URL
The URL for the database connection. *Example:* `postgres://hde:password@db:5432/hope_dedupe_engine`

##### SECRET_KEY
A secret key for the Django installation. *Example:* `django-insecure-pretty-strong`

#### Root directories

#### DEEPFACE_HOME
The root directory for storing model weights for the DeepFace library. *Example:* `/var/hope_dedupe_engine/deepface`

!!! warning "Model Weights Needed"
    In this directory, the model weights files for the chosen model(s) will be stored. These files are essential for the application to function correctly. Without them, the application will not work. To download the required weights, run the following command:

        docker run -it unicef/hope-dedupe-engine:release-0.x django-admin syncmodels

    By default, the `syncmodels` command checks if the files already exist and skips downloading them if they do. To forcefully re-download the files, you can run the command with the `--force` flag:

        docker run -it unicef/hope-dedupe-engine:release-0.x django-admin syncmodels --force

    This directory must be mounted as a shared volume with:

    - **Write** permissions for the container running the backend service.
    - **Read-only** permissions for the containers running the Celery workers.

##### MEDIA_ROOT
The root directory for media files. *Example:* `/var/hope_dedupe_engine/media`

##### STATIC_ROOT
The root directory for static files. *Example:* `/var/hope_dedupe_engine/static`

#### Storage backends

##### FILE_STORAGE_HOPE
This backend is used for storing HOPE dataset images. It should be configured as read-only for the service.
    ```
    FILE_STORAGE_HOPE="storages.backends.azure_storage.AzureStorage?account_name=<account_name>&account_key=<account_key>&azure_container=hope"
    ```
##### FILE_STORAGE_MEDIA
This backend is used for storing media files.

##### FILE_STORAGE_STATIC
This backend is used for storing static files, such as CSS, JavaScript, and images.

## Running the Application

To get the application up and running, follow the steps outlined below. The first command will set up the initial configuration, while the subsequent commands will start the server and related support services, including worker processes and task scheduling.

### Initial Setup

Before starting the application, perform the initial setup using the following command. This will configure the necessary environment settings and prepare the application for runtime:

        docker run -d -t  unicef/hope-dedupe-engine:release-0.x setup

### Starting the Server and Services

Once the initial setup is complete, run the commands below to start the server and the required background services:

    docker run -d -t  unicef/hope-dedupe-engine:release-0.x run
    docker run -d -t  unicef/hope-dedupe-engine:release-0.x worker
    docker run -d -t  unicef/hope-dedupe-engine:release-0.x beat

These commands will ensure that the application server, worker processes, and task scheduler are all running in the background, allowing the full functionality of the application to be available.
