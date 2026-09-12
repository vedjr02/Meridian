"""Reproducible acquisition of the raw event log.

The raw BPI Challenge file is not committed: it is ~30 MB and distributed under the
4TU.ResearchData General Terms of Use. The repository commits this downloader instead.
Running `python -m meridian.datasets` places a byte-identical, checksum-verified copy of the
log in `data/raw/`.
"""

from __future__ import annotations

import argparse
import hashlib
import logging
import os
import shutil
import sys
import tempfile
import urllib.request
from pathlib import Path

from meridian.config import DatasetSource, get_settings

logger = logging.getLogger(__name__)

_CHUNK_BYTES = 1 << 20


class ChecksumMismatchError(RuntimeError):
    """Raised when a downloaded file's SHA-256 does not match the pinned value.

    A dedicated type (not a bare RuntimeError) lets callers and tests distinguish "the upstream
    file changed or the transfer was corrupted" from ordinary network failures.
    """


def sha256_of(path: Path) -> str:
    """Return the hex SHA-256 digest of a file, reading it in chunks.

    Why chunked: event logs can run to hundreds of megabytes uncompressed; verifying one should
    not require loading the whole file into memory.
    """
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(_CHUNK_BYTES), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_dataset(source: DatasetSource, dest_dir: Path, *, force: bool = False) -> Path:
    """Download `source` into `dest_dir`, verify its checksum, and return the local path.

    Why download to a temporary file first: if the transfer is interrupted or the checksum
    fails, `dest_dir` never holds a partial file that a later ingestion run could mistake for
    the real log. The file is moved into place only after verification succeeds.

    Why skip when a verified copy exists: the pipeline is re-run often and should not hit the
    4TU server, or need network access at all, once the data is present and intact.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    target = dest_dir / source.filename

    if target.exists() and not force:
        if sha256_of(target) == source.sha256:
            logger.info("Verified copy already present at %s; skipping download.", target)
            return target
        logger.warning("Existing %s fails checksum verification; re-downloading.", target)

    fd, tmp_name = tempfile.mkstemp(dir=dest_dir, prefix=f".{source.filename}.", suffix=".part")
    tmp_path = Path(tmp_name)
    try:
        logger.info("Downloading %s from %s", source.name, source.url)
        with os.fdopen(fd, "wb") as tmp, urllib.request.urlopen(source.url, timeout=60) as resp:
            shutil.copyfileobj(resp, tmp, _CHUNK_BYTES)
        actual = sha256_of(tmp_path)
        if actual != source.sha256:
            raise ChecksumMismatchError(
                f"{source.name}: expected SHA-256 {source.sha256}, got {actual}. The upstream "
                "file may have changed or the transfer was corrupted; refusing to use it."
            )
        tmp_path.replace(target)
    finally:
        tmp_path.unlink(missing_ok=True)

    logger.info("Saved verified copy to %s", target)
    return target


def main(argv: list[str] | None = None) -> int:
    """Command-line entry point: `python -m meridian.datasets [--force]`.

    Why return an exit code instead of calling `sys.exit` here: the function stays callable from
    tests and other scripts without terminating the interpreter.
    """
    parser = argparse.ArgumentParser(description="Download and verify the raw event log.")
    parser.add_argument(
        "--force", action="store_true", help="re-download even if a verified copy exists"
    )
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    settings = get_settings()
    try:
        path = download_dataset(settings.dataset, settings.raw_dir, force=args.force)
    except ChecksumMismatchError as exc:
        logger.error("%s", exc)
        return 1
    print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
