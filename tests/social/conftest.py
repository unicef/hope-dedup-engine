from pytest_factoryboy import register
from testutils.factories import GroupFactory, SystemFactory, UserFactory

register(SystemFactory)
register(UserFactory)
register(GroupFactory)
