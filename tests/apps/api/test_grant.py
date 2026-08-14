from hope_dedup_engine.apps.api.grant import Grant


def test_grant_members_have_name_as_value() -> None:
    assert Grant.API_READ_ONLY.value == "API_READ_ONLY"
    assert Grant.API_DEDUP.value == "API_DEDUP"


def test_grant_choices() -> None:
    assert Grant.choices() == (
        ("API_READ_ONLY", "Api Read Only"),
        ("API_DEDUP", "Api Dedup"),
    )
