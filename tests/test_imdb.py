"""Validate IMDb parsing using official rows and malformed-file boundary cases."""

import gzip
from pathlib import Path

import pytest

from wanna_watch.imdb import iter_ratings, match_ratings


def test_exact_id_join(tmp_path: Path) -> None:
    """Use IDs rather than title strings and preserve official vote counts."""
    path = tmp_path / "ratings.tsv.gz"
    with gzip.open(path, "wt") as output:
        output.write("tconst\taverageRating\tnumVotes\ntt0068646\t9.2\t2255117\ntt0111161\t9.3\t3236712\n")
    assert match_ratings(path, {"tt0111161", "tt0000000"}) == {"tt0111161": (9.3, 3236712)}


@pytest.mark.parametrize(
    "content",
    [
        "id\trating\tvotes\n",
        "tconst\taverageRating\tnumVotes\ntt0111161\t11\t1\n",
        "tconst\taverageRating\tnumVotes\ntt0111161\t9\t-1\n",
        "tconst\taverageRating\tnumVotes\ninvalid\t9\t1\n",
    ],
)
def test_invalid_dataset_rejected(tmp_path: Path, content: str) -> None:
    """Fail before publishing if source columns or rating values are malformed."""
    path = tmp_path / "ratings.tsv.gz"
    with gzip.open(path, "wt") as output:
        output.write(content)
    with pytest.raises(ValueError):
        list(iter_ratings(path))


@pytest.mark.integration
def test_downloaded_official_dataset_is_readable() -> None:
    """Validate all rows in the real downloaded dataset when it is present."""
    path = Path("data/title.ratings.tsv.gz")
    if not path.exists():
        pytest.skip("Download the real IMDb dataset first; no synthetic dataset is substituted.")
    count = sum(1 for _ in iter_ratings(path))
    assert count > 1_000_000
