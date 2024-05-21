from pytest_factoryboy import register

from .base import AutoRegisterModelFactory, TAutoRegisterModelFactory, factories_registry
from .django_celery_beat import PeriodicTaskFactory  # noqa
from .social import SocialAuthUserFactory  # noqa
from .user import ExternalSystemFactory, GroupFactory, SuperUserFactory, User, UserFactory  # noqa
from .userrole import UserRole, UserRoleFactory  # noqa


def get_factory_for_model(_model) -> type[TAutoRegisterModelFactory]:

    class Meta:
        model = _model

    bases = (AutoRegisterModelFactory,)
    if _model in factories_registry:
        return factories_registry[_model]  # noqa

    return register(type(f"{_model._meta.model_name}AutoCreatedFactory", bases, {"Meta": Meta}))  # noqa
