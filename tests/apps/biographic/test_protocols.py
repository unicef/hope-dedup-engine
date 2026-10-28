"""The backend and the protocol must not drift apart.

`ElasticsearchBiographicSearch` satisfies `BiographicSearch` structurally, without
inheriting from it, so nothing fails loudly when the two stop matching. mypy
catches it at the service's call sites; this holds the contract explicitly, for
the real backend and for the fake the service tests run against.
"""

import inspect

import pytest
from testutils.biographic import FakeBiographicSearch

from hope_dedup_engine.apps.biographic.protocols import BiographicSearch
from hope_dedup_engine.apps.biographic.search.backend import ElasticsearchBiographicSearch


def protocol_methods() -> list[str]:
    return sorted(
        name for name, member in vars(BiographicSearch).items() if callable(member) and not name.startswith("_")
    )


def test_the_protocol_declares_the_methods_we_expect():
    """A method silently vanishing from the contract would make the parametrised test pass vacuously."""
    assert protocol_methods() == [
        "delete_by_status",
        "ensure_index",
        "index_exists",
        "index_records",
        "refresh",
        "search",
        "search_many",
        "set_status",
    ]


@pytest.mark.parametrize("name", protocol_methods())
def test_backend_signature_matches_the_protocol(name):
    expected = inspect.signature(getattr(BiographicSearch, name))

    assert inspect.signature(getattr(ElasticsearchBiographicSearch, name)) == expected


@pytest.mark.parametrize("name", protocol_methods())
def test_fake_has_the_protocol_parameters(name):
    """The fake is untyped, so it is held to the parameter names and defaults, not the annotations."""
    expected = inspect.signature(getattr(BiographicSearch, name))
    actual = inspect.signature(getattr(FakeBiographicSearch, name))

    assert list(actual.parameters) == list(expected.parameters)
    assert [p.default for p in actual.parameters.values()] == [p.default for p in expected.parameters.values()]
