"""StarDict writer.

We write this ourselves rather than using PyGlossary, which is otherwise the
right tool for format conversion.  PyGlossary's StarDict writer has a
documented history of emitting files KOReader cannot read (koreader#9455), and
the failure mode of a bad StarDict file is not a crash but a *silent* one:
lookups for words that are physically present in the file return nothing,
because the reader binary-searches an index it assumes is sorted a particular
way.  A dictionary that quietly loses a tenth of its headwords is worse than
one that fails to build, so this module is small, strict and heavily tested.

Files produced, all in ``<out_dir>/<basename>/``:

``<basename>.ifo``
    Plain-text metadata.  First line is a fixed magic string.

``<basename>.idx``
    ``word\\0`` + ``uint32be`` offset + ``uint32be`` size, once per headword,
    sorted by :func:`kdicts.collation.collation_key`.  **The sort order is
    load-bearing** -- see :mod:`kdicts.collation`.

``<basename>.dict`` (or ``.dict.dz``)
    The definition bodies, concatenated, addressed by the idx offsets.

``<basename>.syn``
    ``form\\0`` + ``uint32be`` *index into the idx*, sorted the same way.  This
    is what makes looking up "wielded" land on "wield"; it is the difference
    between a dictionary that works while reading and one that does not.

Install target on a device: ``koreader/data/dict/<basename>/``.
"""

from __future__ import annotations

import struct
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from ..collation import collation_key
from .dictzip import dictzip_file

__all__ = [
    "MAX_WORD_BYTES",
    "IfoMeta",
    "StarDictError",
    "WriteReport",
    "write_stardict",
]

#: StarDict requires an index word to fit in under 256 bytes.
MAX_WORD_BYTES = 255
_U32_MAX = 0xFFFFFFFF


class StarDictError(Exception):
    """A condition that would produce a file readers cannot use."""


@dataclass(slots=True)
class IfoMeta:
    """Contents of the ``.ifo`` file.

    ``description`` is where source attribution lives *inside the artifact*, so
    a file that gets separated from its package still says where it came from.
    """

    bookname: str
    author: str = ""
    email: str = ""
    website: str = ""
    description: str = ""
    #: ``YYYY.MM.DD``.
    date: str = ""
    #: ``h`` = HTML, ``m`` = plain text, ``x`` = XDXF.  KOReader renders all
    #: three; ``h`` is what lets us show parts of speech and examples distinctly.
    sametypesequence: str = "h"
    #: 2.4.2 keeps offsets at 32 bits and needs no ``idxoffsetbits`` field.
    #: 3.0.0 support for 64-bit offsets is patchy in readers, so we stay here
    #: and refuse to build anything that would overflow.
    version: str = "2.4.2"


@dataclass(slots=True)
class WriteReport:
    """What was written, and what was dropped on the way."""

    directory: Path
    ifo_path: Path
    idx_path: Path
    dict_path: Path
    syn_path: Path | None
    wordcount: int
    synwordcount: int
    idxfilesize: int
    dictfilesize: int
    #: ``(headword, reason)`` for every input rejected in non-strict mode.
    skipped: list[tuple[str, str]] = field(default_factory=list)
    #: Headwords that arrived more than once and had their bodies merged.
    merged_duplicates: int = 0
    #: Synonyms dropped because their target headword does not exist.
    dangling_synonyms: int = 0

    @property
    def total_files(self) -> int:
        return 3 + (1 if self.syn_path else 0)


def _clean_word(word: str) -> tuple[bytes, str | None]:
    """Return ``(encoded, rejection_reason)`` for a candidate index word."""
    cleaned = " ".join(word.split())
    if not cleaned:
        return b"", "empty after whitespace normalisation"
    encoded = cleaned.encode("utf-8")
    if b"\x00" in encoded:
        return encoded, "contains a NUL byte"
    if len(encoded) > MAX_WORD_BYTES:
        return encoded, f"{len(encoded)} bytes exceeds the {MAX_WORD_BYTES}-byte index limit"
    return encoded, None


def _ifo_value(value: str) -> str:
    """Flatten a value to one line.

    The ``.ifo`` parser splits on the first ``=`` of each line, so an embedded
    newline silently truncates everything after it -- which for ``description``
    means losing the attribution.  StarDict's own documentation says to use
    ``<br>`` for line breaks, so that is what we do.
    """
    return value.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "<br>").strip()


def write_stardict(
    out_dir: Path | str,
    basename: str,
    entries: Iterable[tuple[str, str]],
    meta: IfoMeta,
    *,
    synonyms: Iterable[tuple[str, str]] | Mapping[str, Sequence[str]] = (),
    compress: bool = True,
    strict: bool = False,
    merge_duplicates: bool = True,
) -> WriteReport:
    """Write a StarDict dictionary.

    :param entries: ``(headword, definition)`` pairs. Definitions are UTF-8 text
        whose markup must match ``meta.sametypesequence``.
    :param synonyms: ``(inflected_form, headword)`` pairs, or a mapping from
        headword to its forms. Forms whose headword is absent are dropped.
    :param compress: emit ``.dict.dz`` instead of ``.dict``.
    :param strict: raise on any rejected input instead of recording it in
        :attr:`WriteReport.skipped`.
    :param merge_duplicates: concatenate the bodies of repeated headwords. With
        ``False``, a repeat is a rejection.
    """
    directory = Path(out_dir) / basename
    directory.mkdir(parents=True, exist_ok=True)
    skipped: list[tuple[str, str]] = []

    def reject(word: str, reason: str) -> None:
        if strict:
            raise StarDictError(f"{word!r}: {reason}")
        skipped.append((word, reason))

    # --- collect and de-duplicate -------------------------------------------
    bodies: dict[bytes, bytes] = {}
    merged = 0
    for word, definition in entries:
        encoded, reason = _clean_word(word)
        if reason is not None:
            reject(word, reason)
            continue
        body = definition.encode("utf-8")
        if b"\x00" in body:
            # With sametypesequence set the body length comes from the .idx, but
            # readers that hand the buffer to C string routines truncate at the
            # first NUL. Never emit one.
            reject(word, "definition contains a NUL byte")
            continue
        if not body:
            reject(word, "empty definition")
            continue
        previous = bodies.get(encoded)
        if previous is None:
            bodies[encoded] = body
        elif merge_duplicates:
            bodies[encoded] = previous + body
            merged += 1
        else:
            reject(word, "duplicate headword")

    if not bodies:
        raise StarDictError("refusing to write a dictionary with zero entries")

    # --- sort: this is the part that must be right --------------------------
    words = sorted(bodies, key=collation_key)
    positions = {encoded: index for index, encoded in enumerate(words)}

    # --- .dict --------------------------------------------------------------
    raw_dict_path = directory / f"{basename}.dict"
    offsets: list[tuple[int, int]] = []
    cursor = 0
    with raw_dict_path.open("wb") as handle:
        for encoded in words:
            body = bodies[encoded]
            if len(body) > _U32_MAX:
                raise StarDictError(f"{encoded!r}: definition exceeds the 32-bit size field")
            offsets.append((cursor, len(body)))
            cursor += handle.write(body)
            if cursor > _U32_MAX:
                raise StarDictError(
                    "the .dict body exceeded 4 GiB; 32-bit offsets cannot address it. "
                    "Split the dictionary rather than moving to idxoffsetbits=64, "
                    "which many readers do not implement."
                )
    dictfilesize = cursor

    # --- .idx ---------------------------------------------------------------
    idx_path = directory / f"{basename}.idx"
    with idx_path.open("wb") as handle:
        for encoded, (offset, size) in zip(words, offsets, strict=True):
            handle.write(encoded)
            handle.write(b"\x00")
            handle.write(struct.pack(">II", offset, size))
    idxfilesize = idx_path.stat().st_size

    # --- .syn ---------------------------------------------------------------
    syn_pairs = synonyms.items() if isinstance(synonyms, Mapping) else None
    flat: list[tuple[str, str]] = []
    if syn_pairs is not None:
        for headword, forms in syn_pairs:
            flat.extend((form, headword) for form in forms)
    else:
        flat = list(synonyms)  # type: ignore[arg-type]

    syn_records: list[tuple[bytes, int]] = []
    dangling = 0
    seen_syn: set[tuple[bytes, int]] = set()
    for form, headword in flat:
        target, _ = _clean_word(headword)
        index = positions.get(target)
        if index is None:
            dangling += 1
            continue
        encoded, reason = _clean_word(form)
        if reason is not None:
            reject(form, f"synonym: {reason}")
            continue
        if encoded == target:
            # A form identical to its own headword adds nothing: the idx lookup
            # already finds it. Keep the file small.
            continue
        record = (encoded, index)
        if record in seen_syn:
            continue
        seen_syn.add(record)
        syn_records.append(record)

    syn_path: Path | None = None
    if syn_records:
        # Same collation as the idx: the reader binary-searches this file too.
        syn_records.sort(key=lambda item: (collation_key(item[0]), item[1]))
        syn_path = directory / f"{basename}.syn"
        with syn_path.open("wb") as handle:
            for encoded, index in syn_records:
                handle.write(encoded)
                handle.write(b"\x00")
                handle.write(struct.pack(">I", index))

    # --- compress -----------------------------------------------------------
    dict_path = raw_dict_path
    if compress:
        dict_path = directory / f"{basename}.dict.dz"
        dictzip_file(raw_dict_path, dict_path)
        raw_dict_path.unlink()

    # --- .ifo ---------------------------------------------------------------
    ifo_path = directory / f"{basename}.ifo"
    lines = [
        "StarDict's dict ifo file",
        f"version={meta.version}",
        f"bookname={_ifo_value(meta.bookname)}",
        f"wordcount={len(words)}",
    ]
    if syn_records:
        lines.append(f"synwordcount={len(syn_records)}")
    lines.append(f"idxfilesize={idxfilesize}")
    for key, value in (
        ("author", meta.author),
        ("email", meta.email),
        ("website", meta.website),
        ("description", meta.description),
        ("date", meta.date),
    ):
        if value:
            lines.append(f"{key}={_ifo_value(value)}")
    lines.append(f"sametypesequence={meta.sametypesequence}")
    ifo_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    return WriteReport(
        directory=directory,
        ifo_path=ifo_path,
        idx_path=idx_path,
        dict_path=dict_path,
        syn_path=syn_path,
        wordcount=len(words),
        synwordcount=len(syn_records),
        idxfilesize=idxfilesize,
        dictfilesize=dictfilesize,
        skipped=skipped,
        merged_duplicates=merged,
        dangling_synonyms=dangling,
    )
