from unicef_security.models import AbstractUser, SecurityMixin


class User(SecurityMixin, AbstractUser):
    class Meta:
        app_label = "core"
