"""The contract every source adapter implements.

Adding a data source must mean writing one adapter and touching nothing else.
The core never imports a concrete adapter; :mod:`kdicts.sources` looks them up
by the ``kind`` string in the config.

There are two shapes of source and the merger treats them very differently:

:class:`SynsetSource`
    Maps lemmas in one language onto Princeton WordNet 3.0 synset ids.  These
    are the primary mechanism: two of them in two languages produce a bilingual
    dictionary through the pivot, with no direct A-B resource involved.

:class:`BilingualSource`
    Provides direct A->B translations (Wiktionary translation tables, FreeDict,
    WikDict).  These are an *enrichment* layer laid over the pivot output: they
    cover the informal, idiomatic and very recent vocabulary wordnets lack, but
    they cannot generate a new pair on their own.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO, Protocol, runtime_checkable

from ..ir import Entry, Pos, Provenance, SynsetId

__all__ = [
    "BilingualSource",
    "LemmaRecord",
    "SourceError",
    "SourceSpec",
    "SynsetRecord",
    "SynsetSource",
]


class SourceError(Exception):
    """A source could not be read, or refused to declare its licence."""


@dataclass(slots=True)
class SourceSpec:
    """Config for one source instance, read from ``configs/sources.toml``."""

    id: str
    kind: str
    #: Where the fetched data lives, relative to the data root.
    path: str
    lang: str = ""
    url: str = ""
    version: str = ""
    credit: str = ""
    #: Expected checksum of the downloaded artifact. Empty means "unpinned",
    #: which is fine for a first run and a mistake for a scheduled rebuild:
    #: without it, upstream can change the data under a published dictionary.
    sha256: str = ""
    #: Path inside the downloaded archive that becomes ``path``.
    archive_member: str = ""
    #: Explicit licence id.  Adapters that can parse a licence out of the data
    #: must still agree with this when both are present -- a mismatch is a hard
    #: error, because it means the upstream terms changed under us.
    license_id: str = ""
    options: dict[str, object] = field(default_factory=dict)

    def provenance(self, license_id: str | None = None) -> Provenance:
        return Provenance(
            source_id=self.id,
            license_id=license_id or self.license_id,
            credit=self.credit,
            version=self.version,
        )


@dataclass(slots=True)
class LemmaRecord:
    """One (lemma, synset) mapping in one language."""

    lemma: str
    synset: SynsetId
    #: Sense number within the lemma, 1-based; lower is more frequent.
    rank: int = 0
    #: How often this exact (lemma, synset) pairing was actually tagged in a
    #: sense-annotated corpus. This is real usage evidence rather than an
    #: editorial ordering, and it is the only signal we have that can compare
    #: senses *across* parts of speech. 0 means "never tagged", not "rare".
    frequency: int = 0


@dataclass(slots=True)
class SynsetRecord:
    """A synset's own content, in whatever language the source is written in."""

    synset: SynsetId
    pos: Pos
    gloss: str = ""
    examples: tuple[str, ...] = ()


@runtime_checkable
class SynsetSource(Protocol):
    """A source that anchors lemmas to PWN 3.0 synset ids."""

    spec: SourceSpec

    @property
    def lang(self) -> str: ...

    @property
    def license_id(self) -> str: ...

    def lemmas(self) -> Iterator[LemmaRecord]: ...

    def synsets(self) -> Iterator[SynsetRecord]:
        """Glosses and examples, where the source has them. May be empty."""
        ...


@runtime_checkable
class BilingualSource(Protocol):
    """A source of direct A->B material used to enrich pivot output."""

    spec: SourceSpec

    @property
    def source_lang(self) -> str: ...

    @property
    def target_lang(self) -> str: ...

    @property
    def license_id(self) -> str: ...

    def entries(self) -> Iterator[Entry]: ...


def require_existing(path: Path, spec: SourceSpec) -> Path:
    if not path.exists():
        raise SourceError(
            f"source {spec.id!r}: {path} is missing. Run `kdicts fetch {spec.id}` first; "
            "data files are never committed to the repository."
        )
    return path


def open_maybe_gzip(path: Path) -> IO[str]:
    """Open a text file, transparently handling ``.gz``."""
    if path.suffix == ".gz":
        import gzip

        return gzip.open(path, "rt", encoding="utf-8")
    return path.open("r", encoding="utf-8")


def dedupe_preserving_order(items: Iterable[str]) -> tuple[str, ...]:
    seen: dict[str, None] = {}
    for item in items:
        if item:
            seen.setdefault(item, None)
    return tuple(seen)
