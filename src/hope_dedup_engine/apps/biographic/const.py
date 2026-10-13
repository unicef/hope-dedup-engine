from typing import Final

# Enqueued by name: the task bodies belong to the service layer, in `celery_tasks`,
# which is the module Celery autodiscovers.
PROCESS_DATASET_TASK: Final[str] = "hope_dedup_engine.apps.biographic.celery_tasks.process_biographic_dataset"
UPDATE_STATUS_TASK: Final[str] = "hope_dedup_engine.apps.biographic.celery_tasks.update_biographic_status"
