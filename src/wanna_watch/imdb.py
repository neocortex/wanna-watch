"""Download IMDb's official ratings dataset and join it using exact IMDb IDs."""

import csv
import gzip
import json
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import httpx

RATINGS_URL = "https://datasets.imdbws.com/title.ratings.tsv.gz"


def download_ratings(directory: Path) -> tuple[Path, str]:
    """Cache today's complete compressed dataset using an atomic download.

    Args:
        directory: Private directory for downloaded data.

    Returns:
        Dataset path and the source's Last-Modified timestamp.
    """
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "title.ratings.tsv.gz"
    metadata_path = directory / "ratings-source.json"
    today = datetime.now(UTC).date().isoformat()
    if path.exists() and metadata_path.exists():
        metadata = json.loads(metadata_path.read_text())
        if metadata["download_date"] == today:
            return path, metadata["last_modified"]
    temporary = path.with_suffix(".download")
    try:
        with httpx.stream("GET", RATINGS_URL, timeout=120, follow_redirects=True) as response:
            response.raise_for_status()
            with temporary.open("wb") as output:
                for chunk in response.iter_bytes():
                    output.write(chunk)
            modified = response.headers.get("last-modified", datetime.now(UTC).isoformat())
        # Reason: read through gzip's checksum before replacing a usable cached dataset.
        with gzip.open(temporary, "rb") as source:
            while source.read(1024 * 1024):
                pass
        temporary.replace(path)
        metadata_path.write_text(json.dumps({"download_date": today, "last_modified": modified}))
    finally:
        temporary.unlink(missing_ok=True)
    return path, modified


def iter_ratings(path: Path) -> Iterator[tuple[str, float, int]]:
    """Read and validate official IMDb rating rows without loading the entire file.

    Args:
        path: A gzip-compressed title.ratings.tsv dataset.

    Yields:
        IMDb ID, IMDb rating, and IMDb vote count.

    Raises:
        ValueError: The dataset schema or a rating row is invalid.
    """
    with gzip.open(path, "rt", encoding="utf-8", newline="") as source:
        reader = csv.DictReader(source, delimiter="\t")
        if reader.fieldnames != ["tconst", "averageRating", "numVotes"]:
            raise ValueError("Unexpected IMDb ratings schema.")
        for row in reader:
            imdb_id, rating, votes = row["tconst"], float(row["averageRating"]), int(row["numVotes"])
            if not imdb_id.startswith("tt") or not imdb_id[2:].isdigit() or not 0 <= rating <= 10 or votes < 0:
                raise ValueError("Invalid IMDb rating row.")
            yield imdb_id, rating, votes


def match_ratings(path: Path, imdb_ids: set[str]) -> dict[str, tuple[float, int]]:
    """Return ratings for the exact requested IMDb IDs.

    Args:
        path: Official compressed dataset.
        imdb_ids: IDs attached to TMDB movies; titles are never fuzzy-matched.

    Returns:
        Mapping from available IMDb IDs to rating and vote count.
    """
    return {key: (rating, votes) for key, rating, votes in iter_ratings(path) if key in imdb_ids}
