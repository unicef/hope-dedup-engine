import pytest

from ..factories import UserFactory


@pytest.mark.django_db
def test_user():
    user = UserFactory(username="User")
    assert str(user) == "User"
