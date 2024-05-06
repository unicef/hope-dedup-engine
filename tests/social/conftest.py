from pytest_factoryboy import register
from testutils.factories import ExternalSystemFactory, GroupFactory, UserFactory

register(ExternalSystemFactory)
register(UserFactory)
register(GroupFactory)
