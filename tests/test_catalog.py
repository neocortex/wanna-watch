"""Check country and payment filtering using explicit boundary inputs, without mock APIs."""

import pytest

from wanna_watch.catalog import subscription_offers
from wanna_watch.tmdb import TMDB, SourceError


@pytest.mark.parametrize(
    ("offers", "selected", "expected"),
    [
        ({"DE": {"flatrate": [{"provider_id": 8}]}}, {8}, [8]),
        ({"US": {"flatrate": [{"provider_id": 8}]}}, {8}, []),
        ({"DE": {"rent": [{"provider_id": 8}], "buy": [{"provider_id": 8}]}}, {8}, []),
        ({"DE": {"flatrate": [{"provider_id": 9}], "rent": [{"provider_id": 8}]}}, {8}, []),
        ({"DE": {"flatrate": [{"provider_id": 8}, {"provider_id": 9}]}}, {8, 9}, [8, 9]),
        ({}, {8}, []),
        ({"DE": {"flatrate": [{"provider_id": 8}]}}, set(), []),
    ],
)
def test_exact_subscription_country_and_monetization(offers: dict, selected: set[int], expected: list[int]) -> None:
    """Never treat another country, a rental, or an unselected channel as included."""
    movie = {"watch/providers": {"results": offers}}
    assert [p["provider_id"] for p in subscription_offers(movie, selected)] == expected


def test_missing_appended_offers_fail_instead_of_silently_omitting() -> None:
    """Reject a broken enrichment response rather than publish an incomplete catalog."""
    with pytest.raises(KeyError):
        subscription_offers({}, {8})


def test_missing_token_is_actionable() -> None:
    """Require actual credentials instead of substituting a demonstration catalog."""
    with pytest.raises(SourceError, match="TMDB_READ_TOKEN"):
        TMDB("")
