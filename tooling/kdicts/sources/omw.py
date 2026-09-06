"""Open Multilingual Wordnet ``.tab`` files.

Every wordnet in OMW is keyed on Princeton WordNet 3.0 synset ids, which is the
entire reason the pivot works.  It is also where the licensing lands us in
trouble: **each wordnet in OMW carries its own licence**, they are not uniform,
and at least one (WOLF, French) is under CeCILL-C, which cannot be redistributed
as part of a CC BY-SA bundle.  So this adapter parses the licence out of the
file header and refuses to proceed when it cannot, rather than defaulting to
something convenient.

File format -- a comment header, then tab-separated triples::

    # Portuguese  http://openwordnet-pt.org  CC BY-SA
    00001740-n	por:lemma	coisa
    00001740-n	por:def	uma entidade abstrata
    00001740-n	por:exe	uma coisa qualquer
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

from ..ir import Pos, canonical_synset
from .base import (
    LemmaRecord,
    SourceError,
    SourceSpec,
    SynsetRecord,
    open_maybe_gzip,
    require_existing,
)

__all__ = ["LICENSE_PATTERNS", "OmwTabSource", "detect_license"]

_SYNSET_RE = re.compile(r"^\d{8}-[nvars]$")

#: Ordered most specific first: an unversioned "CC BY-SA" must not match before
#: "CC BY-SA 4.0" has had its chance.
LICENSE_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"creativecommons\.org/publicdomain/zero", "CC0-1.0"),
    (r"\bcc[\s\-]?0\b", "CC0-1.0"),
    (r"creativecommons\.org/licenses/by-sa/4\.0", "CC-BY-SA-4.0"),
    (r"creativecommons\.org/licenses/by-sa/3\.0", "CC-BY-SA-3.0"),
    (r"creativecommons\.org/licenses/by/4\.0", "CC-BY-4.0"),
    (r"creativecommons\.org/licenses/by/3\.0", "CC-BY-3.0"),
    (r"creativecommons\.org/licenses/by-nc", "CC-BY-NC-SA-4.0"),
    # Unversioned CC URLs, which is how several OMW lexicons declare themselves
    # (OpenWN-PT and the Romanian wordnet both say ".../licenses/by-sa/").
    (r"creativecommons\.org/licenses/by-sa/?(\s|$|\")", "CC-BY-SA-4.0"),
    (r"creativecommons\.org/licenses/by/?(\s|$|\")", "CC-BY-4.0"),
    (r"opensource\.org/licenses/apache", "Apache-2.0"),
    (r"apache\.org/licenses", "Apache-2.0"),
    (r"\bapache[\s\-]?2", "Apache-2.0"),
    (r"opensource\.org/licenses/mit", "MIT"),
    (r"opendefinition\.org/licenses/odc-by", "ODC-By-1.0"),
    (r"\bodc[\s\-]?by\b", "ODC-By-1.0"),
    (r"wordnet\.princeton\.edu/license", "WordNet-3.0"),
    (r"\bcc[\s\-]?by[\s\-]?sa[\s\-]?4(\.0)?\b", "CC-BY-SA-4.0"),
    (r"\bcc[\s\-]?by[\s\-]?sa[\s\-]?3(\.0)?\b", "CC-BY-SA-3.0"),
    (r"\bcc[\s\-]?by[\s\-]?nc", "CC-BY-NC-SA-4.0"),
    (r"\bcc[\s\-]?by[\s\-]?4(\.0)?\b", "CC-BY-4.0"),
    (r"\bcc[\s\-]?by[\s\-]?3(\.0)?\b", "CC-BY-3.0"),
    # Unversioned "CC BY-SA". We resolve it to 4.0 deliberately: 4.0 has the
    # emptiest outbound set in our licence lattice, so this is the reading that
    # constrains bundling the most. Guessing 3.0 would let us relicense material
    # downward on no evidence. OpenWN-PT lands here.
    (r"\bcc[\s\-]?by[\s\-]?sa\b", "CC-BY-SA-4.0"),
    (r"\bcc[\s\-]?by\b", "CC-BY-4.0"),
    # Not \bcecill: the CeCILL-C URL spells it "Licence_CeCILL-C_V1", and an
    # underscore is a word character, so a leading word boundary never matches.
    (r"cecill[\s\-_]?c(?![a-z])", "CECILL-C"),
    (r"\bgpl[\s\-]?3", "GPL-3.0-or-later"),
    (r"\bgpl[\s\-]?2", "GPL-2.0-or-later"),
    (r"\bmit\b", "MIT"),
    # Several OMW lexicons declare their licence as the bare token "wordnet",
    # meaning the Princeton WordNet licence.
    (r"^\s*wordnet\s*$", "WordNet-3.0"),
    (r"\bwordnet licen[cs]e\b", "WordNet-3.0"),
)


def detect_license(header: str) -> str:
    """Best-effort licence id for an OMW header block.

    Returns ``"UNKNOWN"`` when nothing matches, which :mod:`kdicts.licensing`
    treats as an excluded licence -- the bundler then fails loudly instead of
    shipping material on terms nobody established.
    """
    haystack = header.lower()
    for pattern, license_id in LICENSE_PATTERNS:
        if re.search(pattern, haystack):
            return license_id
    return "UNKNOWN"


class OmwTabSource:
    """Reader for one ``wn-data-<lang>.tab`` file."""

    def __init__(self, spec: SourceSpec, path: Path) -> None:
        self.spec = spec
        self.path = require_existing(Path(path), spec)
        self.header = self._read_header()
        self.detected_license = detect_license(self.header)

        declared = spec.license_id
        if declared and declared != self.detected_license:
            if self.detected_license == "UNKNOWN":
                # The config author looked at the file and we could not parse
                # it. Trust the human, but leave a trace in the header record.
                pass
            else:
                raise SourceError(
                    f"source {spec.id!r}: config declares licence {declared!r} but the "
                    f"file header says {self.detected_license!r}. Upstream terms may have "
                    f"changed. Header was:\n{self.header.strip()}"
                )
        if not declared and self.detected_license == "UNKNOWN":
            raise SourceError(
                f"source {spec.id!r}: could not determine a licence from {self.path}. "
                "Every wordnet in OMW has its own terms; declare license_id explicitly "
                f"in the source config after reading the header:\n{self.header.strip()}"
            )

    def _read_header(self) -> str:
        lines: list[str] = []
        with open_maybe_gzip(self.path) as handle:
            for line in handle:
                if not line.startswith("#"):
                    break
                lines.append(line.lstrip("#").strip())
        return "\n".join(lines)

    @property
    def lang(self) -> str:
        return self.spec.lang

    @property
    def license_id(self) -> str:
        return self.spec.license_id or self.detected_license

    # -- reading -------------------------------------------------------------

    def _rows(self) -> Iterator[tuple[str, str, str]]:
        with open_maybe_gzip(self.path) as handle:
            for number, line in enumerate(handle, start=1):
                if line.startswith("#") or not line.strip():
                    continue
                parts = line.rstrip("\n").split("\t")
                if len(parts) < 3:
                    continue
                synset, key, value = parts[0], parts[1], "\t".join(parts[2:]).strip()
                if not _SYNSET_RE.match(synset):
                    raise SourceError(
                        f"{self.path}:{number}: {synset!r} is not a PWN 3.0 synset id. "
                        "This file is not keyed to WordNet 3.0 and cannot be pivoted."
                    )
                _, _, kind = key.partition(":")
                # Older .tab distributions spell satellite adjectives "-s";
                # OMW 1.4 spells them "-a". Canonicalise so the two can be
                # mixed in one build.
                yield canonical_synset(synset[:-2], synset[-1]), kind or key, value

    def lemmas(self) -> Iterator[LemmaRecord]:
        # OMW files carry no sense-frequency information, so rank is the order
        # the lemmas appear in for a given synset -- which is at least stable.
        seen: dict[str, int] = {}
        for synset, kind, value in self._rows():
            if kind != "lemma" or not value:
                continue
            rank = seen.get(synset, 0) + 1
            seen[synset] = rank
            yield LemmaRecord(lemma=value.replace("_", " "), synset=synset, rank=rank)

    def synsets(self) -> Iterator[SynsetRecord]:
        """Target-language definitions and examples, where the wordnet has them.

        Most OMW wordnets have lemmas only. The ones that carry ``def`` rows
        (OpenWN-PT among them) give us a definition in the *reader's* language,
        which is much more useful than an English gloss.
        """
        glosses: dict[str, str] = {}
        examples: dict[str, list[str]] = {}
        for synset, kind, value in self._rows():
            if kind == "def" and value:
                glosses.setdefault(synset, value)
            elif kind == "exe" and value:
                examples.setdefault(synset, []).append(value)
        for synset in sorted(set(glosses) | set(examples)):
            yield SynsetRecord(
                synset=synset,
                pos=Pos.from_wordnet_tag(synset[-1]),
                gloss=glosses.get(synset, ""),
                examples=tuple(examples.get(synset, ())),
            )
