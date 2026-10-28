from typing import Final

# Task names, as Celery registers them from `celery_tasks`, the module it
# autodiscovers. `BiographicJob` queues the first; the others are sent by name
# so the API layer never imports the task bodies.
PROCESS_DATASET_TASK: Final[str] = "hope_dedup_engine.apps.biographic.celery_tasks.process_biographic_dataset"
UPDATE_STATUS_TASK: Final[str] = "hope_dedup_engine.apps.biographic.celery_tasks.update_biographic_status"
REBUILD_INDEX_TASK: Final[str] = "hope_dedup_engine.apps.biographic.celery_tasks.rebuild_biographic_index"
CLEANUP_REJECTED_TASK: Final[str] = "hope_dedup_engine.apps.biographic.celery_tasks.cleanup_biographic_rejected"

# The daily cleanup's `PeriodicTask`, created by a data migration.
CLEANUP_REJECTED_PERIODIC_TASK_NAME: Final[str] = "Biographic: delete rejected documents"
