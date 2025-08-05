import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings

from hope_dedup_engine.apps.security.backends import AnyUserAuthBackend

User = get_user_model()


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("debug_mode", "should_authenticate"),
    [
        (True, True),
        (False, False),
    ],
)
def test_any_user_auth_backend(debug_mode, should_authenticate):
    """
    Test AnyUserAuthBackend with different DEBUG settings.
    """
    with override_settings(DEBUG=debug_mode):
        backend = AnyUserAuthBackend()
        username = "testuser"

        if should_authenticate:
            # Test creating a user
            assert not User.objects.filter(username=username).exists()
            user = backend.authenticate(request=None, username=username)
            assert user is not None
            assert user.username == username
            assert user.is_staff
            assert user.is_active
            assert user.is_superuser

            # Test updating an existing user
            user.is_staff = False
            user.is_superuser = False
            user.is_active = False
            user.save()

            user = backend.authenticate(request=None, username=username)
            user.refresh_from_db()
            assert user.is_staff
            assert user.is_active
            assert user.is_superuser
        else:
            user = backend.authenticate(request=None, username=username)
            assert user is None
            assert not User.objects.filter(username=username).exists()


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_any_user_auth_backend_ignores_existing_password():
    """
    Test AnyUserAuthBackend authenticates a user even with an unusable password.
    """
    backend = AnyUserAuthBackend()
    username = "testuser_unusable_pass"
    user = User.objects.create_user(username=username)
    user.set_unusable_password()
    user.save()

    authenticated_user = backend.authenticate(request=None, username=username)
    assert authenticated_user is not None
    assert authenticated_user.pk == user.pk
    # It should still make it a superuser
    assert authenticated_user.is_superuser
