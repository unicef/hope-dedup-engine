from unittest.mock import Mock

from constance import config

from hope_dedup_engine.apps.social.pipeline import save_to_group


#
def test_save_to_group(db, group, user):
    save_to_group(Mock(), user)
    assert user.groups.first().name == config.NEW_USER_DEFAULT_GROUP
    assert save_to_group(Mock(), None) == {}
