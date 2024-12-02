---
tags:
  - Deduplication
---

## Prerequisites

This project utilizes [PDM](https://pdm-project.org/) as the package manager for managing Python dependencies and environments. 

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

    $ docker run -it -t  unicef/hope-dedupe-engine:release-0.1 django-admin env

### Mandatory Environment Variables
Check Environment Variables

    $ docker run -it -t  unicef/hope-dedupe-engine:release-0.1 django-admin env --check

Ensure the following environment variables are properly configured:

    DATABASE_URL
    SECRET_KEY
    CACHE_URL
    CELERY_BROKER_URL
    MEDIA_ROOT
    STATIC_ROOT
    DEFAULT_ROOT
    FILE_STORAGE_DNN
    FILE_STORAGE_HOPE
    FILE_STORAGE_STATIC
    FILE_STORAGE_MEDIA

### Variables Breakdown

Detailed information about the required environment variables is provided for clarity and proper configuration.

#### Operational

##### DATABASE_URL
The URL for the database connection. *Example:* `postgres://hde:password@db:5432/hope_dedupe_engine`

##### SECRET_KEY
A secret key for the Django installation. *Example:* `django-insecure-pretty-strong`

##### CACHE_URL
The URL for the cache server. *Example:* `redis://redis:6379/1`

##### CELERY_BROKER_URL
The URL for the Celery broker. *Example:* `redis://redis:6379/9`

#### Root directories

##### DEFAULT_ROOT
The root directory for locally stored files. *Example:* `/var/hope_dedupe_engine/default`

##### MEDIA_ROOT
The root directory for media files. *Example:* `/var/hope_dedupe_engine/media`

##### STATIC_ROOT
The root directory for static files. *Example:* `/var/hope_dedupe_engine/static`

#### Storages

##### FILE_STORAGE_DEFAULT
This backend is used for storing locally downloaded DNN model files and encoded data.
    ```
    FILE_STORAGE_DEFAULT=django.core.files.storage.FileSystemStorage
    ```
#####  FILE_STORAGE_DNN
This backend is dedicated to storing DNN model files. Ensure that the following two files are present in this storage:

1. *deploy.prototxt.txt*: Defines the model architecture.
2. *res10_300x300_ssd_iter_140000.caffemodel*: Contains the pre-trained model weights.

The current process involves downloading files from a [GitHub repository](https://github.com/sr6033/face-detection-with-OpenCV-and-DNN) and saving them to this specific Azure Blob Storage using command `django-admin upgrade --with-dnn-setup`, or the specialized`django-admin dnnsetup` command .
In the future, an automated pipeline related to model training could handle file updates.

The storage configuration is as follows:
```
FILE_STORAGE_DNN="storages.backends.azure_storage.AzureStorage?account_name=<account_name>&account_key=<account_key>&overwrite_files=true&azure_container=dnn"
```

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

        docker run -d -t  unicef/hope-dedupe-engine:release-0.1 setup

### Starting the Server and Services

Once the initial setup is complete, run the commands below to start the server and the required background services:

    docker run -d -t  unicef/hope-dedupe-engine:release-0.1 run
    docker run -d -t  unicef/hope-dedupe-engine:release-0.1 worker
    docker run -d -t  unicef/hope-dedupe-engine:release-0.1 beat

These commands will ensure that the application server, worker processes, and task scheduler are all running in the background, allowing the full functionality of the application to be available.
