import pytest

from hope_dedup_engine.apps.api.models import DeduplicationSet


@pytest.fixture
def job_with_encodings(main_job_factory, encoding_factory):
    job = main_job_factory()
    ds = job.deduplication_set
    encoding_factory(deduplication_set=ds, filename="file1.jpg", embedding=None)
    encoding_factory(deduplication_set=ds, filename="file2.jpg", embedding=None)
    return job


@pytest.fixture
def encode_only_job(main_job_factory, encoding_factory):
    job = main_job_factory(encode_only=True)
    encoding_factory(deduplication_set=job.deduplication_set, filename="file1.jpg", embedding=None)
    return job


@pytest.fixture
def processing_job(main_job_factory):
    return main_job_factory(deduplication_set__state=DeduplicationSet.State.PROCESSING)
