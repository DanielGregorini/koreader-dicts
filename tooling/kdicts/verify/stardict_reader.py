"""A StarDict reader that behaves like sdcv, for verifying our own output.

This exists to *disprove* the writer.  It deliberately does not import
:func:`kdicts.collation.collation_key`: the comparator below is transcribed
directly from the C in StarDict and glib, so if the writer's sort key and the
real comparator ever disagree, the binary search here fails to find words that
are in the file -- which is exactly the production failure mode we are trying
to rule out.  A test that reused the writer's own key could not see that.

It also reads ``.dict.dz`` through the random-access chunk table rather than
inflating the whole stream, so the dictzip output is exercised the way a device
exercises it.
"""

from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass
from pathlib import Path

__all__ = [
    "DictzipReader",
    "IdxEntry",
    "StarDictReader",
    "g_ascii_strcasecmp",
    "stardict_strcmp",
]


def _ascii_tolower(byte: int) -> int:
    return byte + 0x20 if 0x41 <= byte <= 0x5A else byte


def g_ascii_strcasecmp(s1: bytes, s2: bytes) -> int:
    """Transcription of glib's ``g_ascii_strcasecmp``.

    Note what it does *not* do: it never touches bytes >= 0x80, and it compares
    as ``guchar``, so 0xC3 is 195 and sorts after 'z'.
    """
    i = 0
    while i < len(s1) and i < len(s2):
        c1 = _ascii_tolower(s1[i])
        c2 = _ascii_tolower(s2[i])
        if c1 != c2:
            return c1 - c2
        i += 1
    # The C loop stops at the NUL terminator; past the end of a Python bytes
    # object the equivalent value is 0.
    tail1 = s1[i] if i < len(s1) else 0
    tail2 = s2[i] if i < len(s2) else 0
    return tail1 - tail2


def _strcmp(s1: bytes, s2: bytes) -> int:
    i = 0
    while i < len(s1) and i < len(s2):
        if s1[i] != s2[i]:
            return s1[i] - s2[i]
        i += 1
    tail1 = s1[i] if i < len(s1) else 0
    tail2 = s2[i] if i < len(s2) else 0
    return tail1 - tail2


def stardict_strcmp(s1: bytes, s2: bytes) -> int:
    """Transcription of StarDict's ``stardict_strcmp``."""
    a = g_ascii_strcasecmp(s1, s2)
    return a if a != 0 else _strcmp(s1, s2)


class DictzipReader:
    """Random-access reader for a ``.dict.dz``, using the ``RA`` chunk table."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        blob = self.path.read_bytes()
        if blob[:2] != b"\x1f\x8b":
            raise ValueError(f"{path}: not a gzip file")
        flags = blob[3]
        if not flags & 0x04:
            raise ValueError(f"{path}: gzip without FEXTRA, not a dictzip file")
        xlen = struct.unpack("<H", blob[10:12])[0]
        extra = blob[12 : 12 + xlen]
        cursor = 12 + xlen
        if flags & 0x08:  # FNAME
            cursor = blob.index(b"\x00", cursor) + 1
        if flags & 0x10:  # FCOMMENT
            cursor = blob.index(b"\x00", cursor) + 1
        if flags & 0x02:  # FHCRC
            cursor += 2

        subfields: dict[bytes, bytes] = {}
        pos = 0
        while pos + 4 <= len(extra):
            si = extra[pos : pos + 2]
            length = struct.unpack("<H", extra[pos + 2 : pos + 4])[0]
            subfields[si] = extra[pos + 4 : pos + 4 + length]
            pos += 4 + length
        if b"RA" not in subfields:
            raise ValueError(f"{path}: gzip has no RA subfield, not a dictzip file")

        ra = subfields[b"RA"]
        _version, self.chunk_length, chunk_count = struct.unpack("<HHH", ra[:6])
        sizes = struct.unpack(f"<{chunk_count}H", ra[6 : 6 + 2 * chunk_count])
        self._blob = blob
        self._chunk_starts: list[int] = []
        offset = cursor
        for size in sizes:
            self._chunk_starts.append(offset)
            offset += size
        self._chunk_sizes = sizes
        self._cache: dict[int, bytes] = {}

    def _chunk(self, index: int) -> bytes:
        cached = self._cache.get(index)
        if cached is None:
            start = self._chunk_starts[index]
            raw = self._blob[start : start + self._chunk_sizes[index]]
            cached = zlib.decompressobj(-zlib.MAX_WBITS).decompress(raw)
            self._cache[index] = cached
        return cached

    def read(self, offset: int, size: int) -> bytes:
        out = bytearray()
        while size > 0:
            index, within = divmod(offset, self.chunk_length)
            if index >= len(self._chunk_starts):
                break
            chunk = self._chunk(index)
            take = chunk[within : within + size]
            if not take:
                break
            out += take
            offset += len(take)
            size -= len(take)
        return bytes(out)

    def close(self) -> None:
        self._cache.clear()


class _PlainReader:
    """Reader for an uncompressed ``.dict``.

    The handle stays open for the life of the object on purpose: this is a
    random-access reader, so a context manager per read would defeat it. The
    owning :class:`StarDictReader` is itself a context manager.
    """

    def __init__(self, path: Path) -> None:
        self._handle = Path(path).open("rb")  # noqa: SIM115

    def read(self, offset: int, size: int) -> bytes:
        self._handle.seek(offset)
        return self._handle.read(size)

    def close(self) -> None:
        self._handle.close()


@dataclass(frozen=True, slots=True)
class IdxEntry:
    word: bytes
    offset: int
    size: int


class StarDictReader:
    """Open a StarDict directory and look words up the way sdcv does."""

    def __init__(self, directory: Path | str, basename: str | None = None) -> None:
        self.directory = Path(directory)
        if basename is None:
            candidates = sorted(self.directory.glob("*.ifo"))
            if len(candidates) != 1:
                raise ValueError(f"{self.directory}: expected exactly one .ifo, found {len(candidates)}")
            basename = candidates[0].stem
        self.basename = basename

        self.ifo: dict[str, str] = {}
        text = (self.directory / f"{basename}.ifo").read_text(encoding="utf-8")
        head, _, rest = text.partition("\n")
        if head.strip() != "StarDict's dict ifo file":
            raise ValueError(f"{basename}.ifo: bad magic line {head!r}")
        for line in rest.splitlines():
            if "=" in line:
                key, _, value = line.partition("=")
                self.ifo[key.strip()] = value

        self.entries: list[IdxEntry] = self._read_idx(self.directory / f"{basename}.idx")
        self.synonyms: list[tuple[bytes, int]] = self._read_syn(self.directory / f"{basename}.syn")
        # Materialised once. Rebuilding these per lookup turns verifying a
        # 170k-entry dictionary into an O(n*m) crawl, and verification is
        # supposed to run on every build.
        self._words: list[bytes] = [entry.word for entry in self.entries]
        self._forms: list[bytes] = [form for form, _ in self.synonyms]

        dz = self.directory / f"{basename}.dict.dz"
        plain = self.directory / f"{basename}.dict"
        self._dict: DictzipReader | _PlainReader
        self._dict = DictzipReader(dz) if dz.exists() else _PlainReader(plain)

    # -- parsing -------------------------------------------------------------

    @staticmethod
    def _read_idx(path: Path) -> list[IdxEntry]:
        blob = path.read_bytes()
        out: list[IdxEntry] = []
        pos = 0
        while pos < len(blob):
            end = blob.index(b"\x00", pos)
            word = blob[pos:end]
            offset, size = struct.unpack(">II", blob[end + 1 : end + 9])
            out.append(IdxEntry(word, offset, size))
            pos = end + 9
        return out

    @staticmethod
    def _read_syn(path: Path) -> list[tuple[bytes, int]]:
        if not path.exists():
            return []
        blob = path.read_bytes()
        out: list[tuple[bytes, int]] = []
        pos = 0
        while pos < len(blob):
            end = blob.index(b"\x00", pos)
            word = blob[pos:end]
            (index,) = struct.unpack(">I", blob[end + 1 : end + 5])
            out.append((word, index))
            pos = end + 5
        return out

    # -- lookup --------------------------------------------------------------

    def _bisect(self, items: list[bytes], needle: bytes) -> int:
        """First position whose word is not less than *needle*, by stardict_strcmp."""
        low, high = 0, len(items)
        while low < high:
            middle = (low + high) // 2
            if stardict_strcmp(items[middle], needle) < 0:
                low = middle + 1
            else:
                high = middle
        return low

    def find_idx(self, word: str) -> list[int]:
        """Indices in the ``.idx`` whose headword equals *word* exactly."""
        needle = word.encode("utf-8")
        words = self._words
        position = self._bisect(words, needle)
        out: list[int] = []
        while position < len(words) and stardict_strcmp(words[position], needle) == 0:
            out.append(position)
            position += 1
        return out

    def find_syn(self, word: str) -> list[int]:
        """Entry indices reachable from *word* through the ``.syn`` file."""
        needle = word.encode("utf-8")
        forms = self._forms
        position = self._bisect(forms, needle)
        out: list[int] = []
        while position < len(forms) and stardict_strcmp(forms[position], needle) == 0:
            out.append(self.synonyms[position][1])
            position += 1
        return out

    def definition_at(self, index: int) -> str:
        entry = self.entries[index]
        return self._dict.read(entry.offset, entry.size).decode("utf-8")

    def lookup(self, word: str, *, follow_synonyms: bool = True) -> list[str]:
        """Definitions for *word*, trying the case variants sdcv tries.

        ``stardict_strcmp`` breaks case ties with ``strcmp``, so an exact search
        for "Dog" does not match the entry "dog".  sdcv papers over this by
        retrying a few case foldings; so do we, because that is what a user on
        a device actually experiences.
        """
        seen: set[int] = set()
        found: list[str] = []
        variants = [word]
        for variant in (word.lower(), word.capitalize(), word.upper()):
            if variant not in variants:
                variants.append(variant)
        for variant in variants:
            indices = list(self.find_idx(variant))
            if follow_synonyms:
                indices += self.find_syn(variant)
            for index in indices:
                if index not in seen:
                    seen.add(index)
                    found.append(self.definition_at(index))
            if found:
                break
        return found

    def headwords(self) -> list[str]:
        return [word.decode("utf-8") for word in self._words]

    def close(self) -> None:
        self._dict.close()

    def __enter__(self) -> StarDictReader:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
