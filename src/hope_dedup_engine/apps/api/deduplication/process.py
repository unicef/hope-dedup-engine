from dataclasses import asdict

from django.db.models import F

from celery import chord, shared_task

from hope_dedup_engine.apps.api.deduplication.config import DeduplicationSetConfig

# from hope_dedup_engine.apps.api.deduplication.registry import (  # DuplicateFinder,; DuplicateKeyPair,
#     get_finders,
# )
from hope_dedup_engine.apps.api.models import DedupJob, DeduplicationSet, Finding
from hope_dedup_engine.apps.api.utils.notification import send_notification

# from hope_dedup_engine.apps.api.utils.progress import track_progress_multi
from hope_dedup_engine.apps.faces.celery_tasks import (
    callback_encodings,
    encode_chunk,
    get_chunks,
    handle_error,
)

# def _sort_keys(pair: DuplicateKeyPair) -> DuplicateKeyPair:
#     first, second, score = pair
#     return *sorted((first, second)), score


# def _save_duplicates(
#     finder: DuplicateFinder,
#     deduplication_set: DeduplicationSet,
#     tracker: Callable[[int], None],
# ) -> None:
#     reference_pk_to_filename_mapping = dict(
#         deduplication_set.image_set.values_list("reference_pk", "filename")
#     )
#     ignored_filename_pairs = frozenset(
#         map(
#             tuple,
#             map(
#                 sorted,
#                 deduplication_set.ignoredfilenamepair_set.values_list(
#                     "first", "second"
#                 ),
#             ),
#         )
#     )

#     ignored_reference_pk_pairs = frozenset(
#         deduplication_set.ignoredreferencepkpair_set.values_list("first", "second")
#     )

#     for first, second, score in map(_sort_keys, finder.run(tracker)):
#         first_filename, second_filename = sorted(
#             (
#                 reference_pk_to_filename_mapping[first],
#                 reference_pk_to_filename_mapping[second],
#             )
#         )
#         ignored = (first, second) in ignored_reference_pk_pairs or (
#             first_filename,
#             second_filename,
#         ) in ignored_filename_pairs
#         if not ignored:
#             duplicate, _ = Duplicate.objects.get_or_create(
#                 deduplication_set=deduplication_set,
#                 first_reference_pk=first,
#                 second_reference_pk=second,
#             )
#             duplicate.score += score * finder.weight
#             duplicate.save()


HOUR = 60 * 60


def update_job_progress(job: DedupJob, progress: int) -> None:
    job.progress = progress
    job.save(update_fields=["progress"])


@shared_task(soft_time_limit=0.5 * HOUR, time_limit=1 * HOUR)
def find_duplicates(dedup_job_id: int, version: int) -> None:
    dedup_job: DedupJob = DedupJob.objects.get(pk=dedup_job_id, version=version)
    deduplication_set = dedup_job.deduplication_set
    try:

        deduplication_set.state = DeduplicationSet.State.DIRTY
        deduplication_set.save(update_fields=["state"])
        send_notification(deduplication_set.notification_url)

        config = asdict(
            DeduplicationSetConfig.from_deduplication_set(deduplication_set)
        )

        # clean results
        Finding.objects.filter(deduplication_set=deduplication_set).delete()
        dedup_job.progress = 0
        dedup_job.save(update_fields=["progress"])

        # weight_total = 0
        # for finder, tracker in zip(
        # for finder, _ in zip(
        #     get_finders(deduplication_set),
        #     track_progress_multi(partial(update_job_progress, dedup_job)),
        # ):
        #     # _save_duplicates(finder, deduplication_set, tracker)
        #     weight_total += finder.weight

        weight_total = 1
        deduplication_set.finding_set.update(score=F("score") / weight_total)

        files = deduplication_set.image_set.values_list("filename", flat=True)
        chunks = get_chunks(files)
        tasks = [encode_chunk.s(chunk, config) for chunk in chunks]
        chord_id = chord(tasks)(callback_encodings.s(config=config))

        # for finder, tracker in zip(
        #     get_finders(deduplication_set),
        #     track_progress_multi(partial(update_job_progress, dedup_job)),
        # ):
        #     for first, second, score in finder.run(tracker):
        #         finding = (first, second, score * finder.weight)
        #         deduplication_set.update_findings(finding)

        deduplication_set.state = deduplication_set.State.CLEAN
        deduplication_set.save(update_fields=["state"])

        return {
            "deduplication_set": str(deduplication_set),
            "chord_id": str(chord_id),
            "chunks": len(chunks),
        }
    except Exception:
        handle_error(deduplication_set)
        raise
