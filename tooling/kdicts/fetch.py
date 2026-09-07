"""Download source data into the local data root.

Source files are never committed. Each one is downloaded on demand, verified
against the checksum in configs/sources.toml, cached under data/.cache and, if
it arrived inside an archive, unpacked to the path the adapter expects.

Standard library only: no third-party HTTP client is needed to fetch a tarball.
"""

from __future__ import annotations

import hashlib
import shutil
import tarfile
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path

__all__ = ["FetchError", "FetchResult", "download", "ensure_source", "extract"]

_USER_AGENT = "koreader-dicts/0.1 (+https://github.com/koreader-dicts)"
_CHUNK = 1 << 20


class FetchError(Exception):
    pass


@dataclass(slots=True)
class FetchResult:
    url: str
    path: Path
    bytes_written: int
    cached: bool
    sha256: str


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(_CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def download(url: str, destination: Path, *, sha256: str = "", force: bool = False) -> FetchResult:
    """Download *url* to *destination*, skipping the transfer if it is current."""
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)

    if destination.exists() and not force:
        digest = _hash_file(destination)
        if not sha256 or digest == sha256:
            return FetchResult(url, destination, destination.stat().st_size, True, digest)

    temporary = destination.with_suffix(destination.suffix + ".part")
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    try:
        with urllib.request.urlopen(request) as response, temporary.open("wb") as handle:
            written = 0
            while chunk := response.read(_CHUNK):
                written += handle.write(chunk)
    except urllib.error.URLError as error:
        temporary.unlink(missing_ok=True)
        raise FetchError(f"{url}: {error}") from error

    digest = _hash_file(temporary)
    if sha256 and digest != sha256:
        temporary.unlink(missing_ok=True)
        raise FetchError(
            f"{url}: sha256 mismatch\n  expected {sha256}\n  got      {digest}\n"
            "Upstream data changed. Verify the new file, then update the checksum in "
            "configs/sources.toml -- do not silently rebuild against unverified data."
        )
    temporary.replace(destination)
    return FetchResult(url, destination, written, False, digest)


def extract(archive: Path, destination: Path) -> Path:
    """Extract a tar or zip archive into *destination*."""
    archive, destination = Path(archive), Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    if tarfile.is_tarfile(archive):
        with tarfile.open(archive) as handle:
            # filter="data" refuses absolute paths, "..", symlinks out of the
            # tree and device nodes. Upstream tarballs are not hostile, but a
            # build farm running unattended should not assume that.
            handle.extractall(destination, filter="data")
    elif zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as handle:
            for member in handle.namelist():
                target = (destination / member).resolve()
                if not str(target).startswith(str(destination.resolve())):
                    raise FetchError(f"{archive}: member {member!r} escapes the destination")
            handle.extractall(destination)
    else:
        raise FetchError(f"{archive}: not a tar or zip archive")
    return destination


def _cache_name(url: str) -> str:
    """Cache filename for *url*, unique to the whole URL and not just its tail.

    Every kaikki edition is published as ``raw-wiktextract-data.jsonl.gz``, so
    naming the cache entry after the last path segment made six different
    downloads collide on one file and silently hand five sources the contents
    of the first. The digest prefix is what makes them distinct; the readable
    tail is kept so the cache stays greppable.
    """
    tail = url.rstrip("/").rsplit("/", 1)[-1] or "download"
    return f"{hashlib.sha256(url.encode()).hexdigest()[:12]}-{tail}"


def ensure_source(
    *,
    url: str,
    data_root: Path,
    relative_path: str,
    cache_dir: Path | None = None,
    sha256: str = "",
    archive_member: str = "",
    force: bool = False,
) -> Path:
    """Make ``data_root / relative_path`` exist, downloading and unpacking if needed.

    *archive_member* names the path inside an archive that should end up at
    *relative_path*; leave it empty when the download is the file itself.
    """
    data_root = Path(data_root)
    target = data_root / relative_path
    if target.exists() and not force:
        return target

    cache_dir = Path(cache_dir or data_root / ".cache")
    filename = _cache_name(url)
    archive = cache_dir / filename
    download(url, archive, sha256=sha256, force=force)

    if not archive_member:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(archive, target)
        return target

    unpacked = cache_dir / f"{filename}.extracted"
    if force and unpacked.exists():
        shutil.rmtree(unpacked)
    if not unpacked.exists():
        extract(archive, unpacked)

    member = unpacked / archive_member
    if not member.exists():
        raise FetchError(
            f"{url}: {archive_member!r} not found in the archive. "
            f"Contents start with: {sorted(p.name for p in unpacked.iterdir())[:10]}"
        )
    target.parent.mkdir(parents=True, exist_ok=True)
    if member.is_dir():
        shutil.copytree(member, target, dirs_exist_ok=True)
    else:
        shutil.copyfile(member, target)
    return target
