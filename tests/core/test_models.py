import pytest

from ..factories import UserFactory


@pytest.mark.django_db
def test_system():
    system = UserFactory(name="Hope")
    assert str(system) == "Hope"
