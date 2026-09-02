from pytest_factoryboy import register
from testutils.factories import GroupFactory, UserFactory

register(UserFactory)
register(GroupFactory)
