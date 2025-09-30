from testutils.factories.api import DedupJobFactory


def test_get_filenames_with_empty_data():
    job = DedupJobFactory.create()
    assert job.get_filenames() == []


def test_get_filenames():
    data = [
        {"filename": "some_sick_file1", "reference_pk": "123456"},
        {"filename": "some_sick_file2", "reference_pk": "123456"},
        {"filename": "some_sick_file2", "reference_pk": "123456"},
    ]
    job = DedupJobFactory.create(files_data=data)
    assert job.get_filenames() == [f.get("filename") for f in data]
