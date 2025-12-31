import pytest
from collections.abc import Callable
from django.core.exceptions import PermissionDenied
from pytest_mock import MockerFixture
from unittest.mock import Mock

from hope_dedup_engine.apps.api.admin import base as admin_base


@pytest.fixture(autouse=True)
def _button_props(mocker: MockerFixture) -> None:
    site = mocker.Mock()
    site.name = "admin"

    mocker.patch.object(admin_base.FixedChoiceButton, "admin_site", new=property(lambda self: site))
    mocker.patch.object(admin_base.FixedChoiceButton, "request", new=property(lambda self: self.context["request"]))
    mocker.patch.object(
        admin_base.FixedChoiceButton, "original", new=property(lambda self: self.context.get("original"))
    )


@pytest.fixture
def mk_handler(mocker: MockerFixture) -> Callable[..., Mock]:
    def _mk(name: str, *, single: bool, perm: str | None = None, label: str | None = None) -> Mock:
        h = mocker.Mock()
        h.name = name
        h.url_name = name
        h.single_object_invocation = single
        h.permission = perm
        h.config = {} if label is None else {"label": label}
        return h

    return _mk


@pytest.fixture
def mk_choice(mocker: MockerFixture) -> Callable[[Mock], Mock]:
    def _mk(handler: Mock) -> Mock:
        cfg = mocker.Mock()
        cfg.func = mocker.Mock()
        cfg.func.extra_buttons_handler = handler
        return cfg

    return _mk


@pytest.fixture
def mk_btn(mocker: MockerFixture) -> Callable[..., admin_base.FixedChoiceButton]:
    def _mk(
        *, choices, change_form: bool, change_list: bool, original=None, path: str = "/x/"
    ) -> admin_base.FixedChoiceButton:
        btn = admin_base.FixedChoiceButton.__new__(admin_base.FixedChoiceButton)
        btn.choices = choices
        btn.change_form = change_form
        btn.change_list = change_list
        btn.context = {"request": mocker.Mock(path=path), **({"original": original} if original is not None else {})}
        btn.visible = True
        btn.authorized = mocker.Mock(return_value=True)
        return btn

    return _mk


@pytest.mark.parametrize(
    ("change_form", "path", "expected"),
    [
        (
            True,
            "/admin:b/1/",
            [
                {"label": "A", "url": "/admin:a/", "selected": False},
                {"label": "LBL:b", "url": "/admin:b/1/", "selected": True},
            ],
        ),
        (
            False,  # b -> url=None
            "/admin:a/",
            [
                {"label": "A", "url": "/admin:a/", "selected": True},
            ],
        ),
    ],
    ids=["change_form", "url_is_none"],
)
def test_fixed_choice_button_get_choices(
    mocker: MockerFixture,
    mk_handler: Callable[..., Mock],
    mk_choice: Callable[[Mock], Mock],
    mk_btn: Callable[..., admin_base.FixedChoiceButton],
    change_form: bool,
    path: str,
    expected: list[dict[str, str | bool]],
) -> None:
    mocker.patch(
        "hope_dedup_engine.apps.api.admin.base.reverse",
        side_effect=lambda name, args=None, **_: f"/{name}/" if not args else f"/{name}/{args[0]}/",
    )
    mocker.patch("hope_dedup_engine.apps.api.admin.base.labelize", side_effect=lambda s: f"LBL:{s}")

    check_permission = mocker.patch("hope_dedup_engine.apps.api.admin.base.check_permission")

    def _perm(_h, perm, *_):
        if perm == "deny":
            raise PermissionDenied

    check_permission.side_effect = _perm

    specs = [("a", True, "allow", "A"), ("b", False, "allow", None), ("c", True, "deny", None)]
    original = mocker.Mock(pk=1)
    handlers = [mk_handler(name, single=single, perm=perm, label=label) for (name, single, perm, label) in specs]

    btn = mk_btn(
        choices=[mk_choice(h) for h in handlers],
        change_form=change_form,
        change_list=True,
        original=original,
        path=path,
    )

    assert list(btn.get_choices()) == expected
    assert check_permission.call_args_list == [
        mocker.call(
            h, h.permission, btn.request, (original if (change_form and not h.single_object_invocation) else None)
        )
        for h in handlers
        if h.permission
    ]


def test_fixed_choice_button_can_render(
    mocker: MockerFixture, mk_btn: Callable[..., admin_base.FixedChoiceButton]
) -> None:
    btn = mk_btn(choices=[], change_form=False, change_list=False)
    btn.authorized.return_value = False
    btn.get_choices = mocker.Mock()
    assert btn.can_render() is False
    btn.get_choices.assert_not_called()
