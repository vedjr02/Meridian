"""Tests for the checksum-verified dataset downloader.

These use local `file://` URLs so the real download code path is exercised without network
access or a dependency on the 4TU server being up.
"""

import hashlib
import urllib.request
from pathlib import Path

import pytest

from meridian.config import DatasetSource
from meridian.datasets import ChecksumMismatchError, download_dataset, sha256_of

PAYLOAD = b"<log><trace><event/></trace></log>" * 1000


def _source_for(tmp_path: Path, payload: bytes, sha256: str | None = None) -> DatasetSource:
    """Write `payload` to a local file and describe it as a downloadable dataset source."""
    origin = tmp_path / "origin" / "log.xes.gz"
    origin.parent.mkdir()
    origin.write_bytes(payload)
    return DatasetSource(
        name="synthetic",
        url=origin.as_uri(),
        filename="log.xes.gz",
        sha256=sha256 or hashlib.sha256(payload).hexdigest(),
    )


def test_sha256_of_matches_hashlib(tmp_path: Path) -> None:
    """Chunked hashing must agree with a one-shot digest, or every verification is meaningless."""
    path = tmp_path / "blob.bin"
    path.write_bytes(PAYLOAD)

    assert sha256_of(path) == hashlib.sha256(PAYLOAD).hexdigest()


def test_download_writes_verified_file(tmp_path: Path) -> None:
    """A successful download lands at the configured filename with the exact source bytes."""
    source = _source_for(tmp_path, PAYLOAD)
    dest = tmp_path / "raw"

    path = download_dataset(source, dest)

    assert path == dest / "log.xes.gz"
    assert path.read_bytes() == PAYLOAD


def test_checksum_mismatch_raises_and_leaves_no_partial_file(tmp_path: Path) -> None:
    """A corrupted or changed upstream file must never be left where ingestion would read it."""
    source = _source_for(tmp_path, PAYLOAD, sha256="0" * 64)
    dest = tmp_path / "raw"

    with pytest.raises(ChecksumMismatchError):
        download_dataset(source, dest)

    assert list(dest.iterdir()) == []


def test_verified_existing_copy_skips_network(tmp_path: Path, monkeypatch) -> None:
    """Re-running the pipeline must not re-download (or need network) once data is intact."""
    source = _source_for(tmp_path, PAYLOAD)
    dest = tmp_path / "raw"
    download_dataset(source, dest)

    def fail_if_called(*args, **kwargs):
        """Stand-in for urlopen that proves no network call happens."""
        raise AssertionError("download attempted despite a verified local copy")

    monkeypatch.setattr(urllib.request, "urlopen", fail_if_called)

    assert download_dataset(source, dest).read_bytes() == PAYLOAD


def test_corrupt_existing_copy_is_replaced(tmp_path: Path) -> None:
    """A local file that fails verification is re-fetched rather than trusted."""
    source = _source_for(tmp_path, PAYLOAD)
    dest = tmp_path / "raw"
    dest.mkdir()
    (dest / "log.xes.gz").write_bytes(b"truncated")

    assert download_dataset(source, dest).read_bytes() == PAYLOAD
