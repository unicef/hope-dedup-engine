from django.contrib.auth.models import Group
from django.db import models

from unicef_security.models import AbstractUser, SecurityMixin


class System(models.Model):
    name = models.CharField(max_length=255)


class User(SecurityMixin, AbstractUser):

    class Meta:
        abstract = False


class UserRole(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    system = models.ForeignKey(System, on_delete=models.CASCADE)
    group = models.ForeignKey(Group, on_delete=models.CASCADE)

    class Meta:
        constraints = (
            models.UniqueConstraint(
                name="%(app_label)s_%(class)s_unique_role",
                fields=["user", "system", "group"],
            ),
        )
