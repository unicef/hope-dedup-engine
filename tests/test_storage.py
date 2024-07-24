from django.core.files.base import ContentFile

import pytest

from hope_dedup_engine.apps.core.storage import CV2DNNStorage, HOPEAzureStorage


def test_fs(tmp_path):
    s = CV2DNNStorage(tmp_path)
    s.save("test", ContentFile("aa", "test.txt"))
    s.save("test", ContentFile("bb", "test.txt"))
    assert s.listdir(".") == ([], ["test"])
    with s.open("test") as fd:
        assert fd.read() == b"bb"
    s.delete("test")


def test_azure(tmp_path):
    s = HOPEAzureStorage()
    with pytest.raises(RuntimeError):
        s.open("test", "rw")
    with pytest.raises(RuntimeError):
        s.save("test", ContentFile("aa", "test.txt"))
    with pytest.raises(RuntimeError):
        s.delete("test")

    # assert s.listdir(".") == ([], [])
    assert s.open("test", "r")
