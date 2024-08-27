The service utilizes following storages:
- **FILE_STORAGE_DEFAULT**: A storage for storing locally downloaded DNN model files and encodings data files.

    ```
    FILE_STORAGE_DEFAULT=django.core.files.storage.FileSystemStorage?location=/var/hope_dedupe_engine/default
    ```

- **FILE_STORAGE_DNN**: A storage for DNN model files. In the future, those files can be updated by a dedicated pipeline from the service that trains the model.
    ```
    FILE_STORAGE_DNN="storages.backends.azure_storage.AzureStorage?account_name=<account_name>&account_key=<account_key>&overwrite_files=true&azure_container=dnn"
    ```

- **FILE_STORAGE_HOPE**: A storage for the HOPE dataset images. This storage must be read-only for the service.
    ```
    FILE_STORAGE_HOPE="storages.backends.azure_storage.AzureStorage?account_name=<account_name>&account_key=<account_key>&azure_container=hope"
    ```

- **FILE_STORAGE_MEDIA**: A storage for media files.

- **FILE_STORAGE_STATIC**: A storage for static files, such as CSS, JavaScript, and images.

