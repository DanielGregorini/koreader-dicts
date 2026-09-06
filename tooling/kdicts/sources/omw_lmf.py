"""Open Multilingual Wordnet 1.4, in the WN-LMF XML it is actually shipped as.

The OMW 1.4 release does **not** contain the ``wn-data-<lang>.tab`` files older
documentation describes; each lexicon is a Global WordNet Association WN-LMF
1.1 document::

    <Lexicon id="omw-pt" label="OpenWN-PT" language="pt"
             license="https://creativecommons.org/licenses/by-sa/" version="1.4">
      <LexicalEntry id="omw-pt-capaz-a">
        <Lemma writtenForm="capaz" partOfSpeech="a"/>
        <Sense id="omw-pt-capaz-00306314-a" synset="omw-pt-00306314-a"/>
      </LexicalEntry>
      <Synset id="omw-pt-00001740-n" ili="i35545" partOfSpeech="n"
              members="omw-pt-ente-00001740-n ..."/>
    </Lexicon>

Two things make this better than the ``.tab`` format for our purposes, and one
makes it worse.

Better: the licence is a machine-readable attribute rather than free text in a
comment, and it is *per lexicon* -- which the release proves is not a formality.
Across the 32 lexicons in 1.4 there are ten distinct licences, including
CeCILL-C (French/WOLF) which cannot be bundled with CC BY-SA material at all,
and CC BY 3.0 (Spanish/MCR) which can.

Worse: the files are large enough that a DOM parse is wasteful, so everything
here streams with :func:`xml.etree.ElementTree.iterparse` and clears elements
as it goes.

Synset ids are namespaced with the lexicon id (``omw-pt-00001740-n``); stripping
that prefix yields the shared PWN 3.0 key the pivot joins on.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path
from xml.etree import ElementTree

from ..ir import Pos, canonical_synset
from .base import LemmaRecord, SourceError, SourceSpec, SynsetRecord, require_existing
from .omw import detect_license

__all__ = ["OmwLmfSource"]

_SYNSET_SUFFIX = re.compile(r"(\d{8})-([nvars])$")


class OmwLmfSource:
    """Reader for one ``omw-<code>/omw-<code>.xml`` lexicon."""

    def __init__(self, spec: SourceSpec, path: Path) -> None:
        self.spec = spec
        self.path = require_existing(Path(path), spec)
        self.lexicon_id, self.label, self.language, self.declared_license, self.version = (
            self._read_header()
        )
        self.detected_license = detect_license(self.declared_license)

        # Every OMW lexicon states its own licence in the XML header. Cross-check
        # it against the config: a mismatch means upstream terms changed, and
        # rebuilding on the old assumption would mislabel the output.
        declared = spec.license_id
        if declared and self.detected_license != "UNKNOWN" and declared != self.detected_license:
            raise SourceError(
                f"source {spec.id!r}: config declares licence {declared!r} but "
                f"{self.path.name} declares {self.declared_license!r} "
                f"({self.detected_license}). Upstream terms may have changed; "
                "check before rebuilding."
            )
        if not declared and self.detected_license == "UNKNOWN":
            raise SourceError(
                f"source {spec.id!r}: could not interpret the licence "
                f"{self.declared_license!r} declared by {self.path.name}. Every OMW "
                "lexicon has its own terms; add license_id to the source config after "
                "reading them."
            )

    def _read_header(self) -> tuple[str, str, str, str, str]:
        # Read only as far as the <Lexicon> start tag. These files run to
        # hundreds of MB and the header carries everything needed up front.
        for _event, element in ElementTree.iterparse(self.path, events=("start",)):
            tag = element.tag.rpartition("}")[2]
            if tag == "Lexicon":
                return (
                    element.get("id", ""),
                    element.get("label", ""),
                    element.get("language", ""),
                    element.get("license", ""),
                    element.get("version", ""),
                )
            if tag not in ("LexicalResource",):
                break
        raise SourceError(f"{self.path}: no <Lexicon> element; not a WN-LMF document")

    @property
    def lang(self) -> str:
        return self.spec.lang or self.language

    @property
    def license_id(self) -> str:
        return self.spec.license_id or self.detected_license

    # -- reading -------------------------------------------------------------

    def _strip_prefix(self, identifier: str) -> str | None:
        """``omw-pt-00001740-n`` -> ``00001740-n``, canonicalised."""
        match = _SYNSET_SUFFIX.search(identifier)
        if not match:
            return None
        return canonical_synset(match.group(1), match.group(2))

    def lemmas(self) -> Iterator[LemmaRecord]:
        context = ElementTree.iterparse(self.path, events=("end",))
        for _event, element in context:
            if element.tag.rpartition("}")[2] != "LexicalEntry":
                continue
            lemma_element = element.find("Lemma")
            written = (lemma_element.get("writtenForm", "") if lemma_element is not None else "")
            written = written.replace("_", " ").strip()
            if written:
                for rank, sense in enumerate(element.findall("Sense"), start=1):
                    synset = self._strip_prefix(sense.get("synset", ""))
                    if synset:
                        yield LemmaRecord(lemma=written, synset=synset, rank=rank)
            element.clear()

    def synsets(self) -> Iterator[SynsetRecord]:
        """Definitions and examples, for the lexicons that have them.

        Most do not: of the 32 lexicons in 1.4 only about a third carry
        ``<Definition>`` elements, and OpenWN-PT is not among them.  That is
        exactly why the pivot falls back to the English WordNet gloss.
        """
        context = ElementTree.iterparse(self.path, events=("end",))
        for _event, element in context:
            if element.tag.rpartition("}")[2] != "Synset":
                continue
            synset = self._strip_prefix(element.get("id", ""))
            if synset:
                definition = element.find("Definition")
                gloss = (definition.text or "").strip() if definition is not None else ""
                examples = tuple(
                    (e.text or "").strip() for e in element.findall("Example") if (e.text or "").strip()
                )
                if gloss or examples:
                    yield SynsetRecord(
                        synset=synset,
                        pos=Pos.from_wordnet_tag(element.get("partOfSpeech", "")),
                        gloss=gloss,
                        examples=examples,
                    )
            element.clear()
