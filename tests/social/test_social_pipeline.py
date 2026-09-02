from constance import config
from pytest_mock import MockerFixture

from hope_dedup_engine.apps.social.pipeline import save_to_group


def test_save_to_group(db, group, user, mocker: MockerFixture):
    save_to_group(mocker.Mock(), user)

    assert config.NEW_USER_DEFAULT_GROUP in user.groups.values_list("name", flat=True)
    assert save_to_group(mocker.Mock(), None) == {}
