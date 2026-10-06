"""The backend and the protocol must not drift apart.

`ElasticsearchBiographicSearch` satisfies `BiographicSearch` structurally, without
inheriting from it, so nothing fails loudly when the two stop matching. mypy would
catch it at a call site, but the only call sites are in the service, which lives in
another issue. Until that exists, this is what holds the contract.
"""

import inspect

import pytest

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
        "index_records",
        "refresh",
        "search",
        "set_status",
    ]


@pytest.mark.parametrize("name", protocol_methods())
def test_backend_signature_matches_the_protocol(name):
    expected = inspect.signature(getattr(BiographicSearch, name))

    assert inspect.signature(getattr(ElasticsearchBiographicSearch, name)) == expected
