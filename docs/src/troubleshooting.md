# **Troubleshooting**

If you encounter issues while running the service, the **admin panel** can be a useful tool for diagnosing and resolving problems. The admin panel provides access to various configurations, logs, and status indicators that can help identify potential causes of issues.


### Reprocessing Deduplication Sets

If you need to rerun the entire cycle of image processing and duplicate detection for a specific deduplication set, you can easily requeue the corresponding job from the admin panel.

To do this:

1. Navigate to:

        Home › Api › Dedup jobs

2. Select the relevant deduplication set.

3. Click the **Queue** button to restart the job. This action will delete all previous findings and process the images again from scratch.

You can monitor the **status** of the Celery tasks related to this process by navigating to:

        Home › Celery Results › Task results

This feature is particularly **useful** if:

- You have updated the configuration of the deuplications set.

- Images have been added or removed from the deduplication set.

- The previous processing attempt was unsuccessful.

By requeuing, you ensure the deduplication set reflects the most accurate and up-to-date results.


### Sentry

To efficiently track and monitor errors within the application, **Sentry** is integrated as the primary tool for error logging and alerting.

!!! warning "Sentry environment"
    For Sentry to work correctly, ensure that the **SENTRY_DSN** environment variable is set.
