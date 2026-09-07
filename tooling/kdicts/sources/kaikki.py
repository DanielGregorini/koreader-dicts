"""Wiktionary via kaikki.org (wiktextract JSONL).

Wiktionary is the enrichment layer, not the spine.  It covers what wordnets
cannot -- slang, idiom, proper nouns, very recent vocabulary -- and it is the
only source that gives us inflected forms in bulk, which is what fills the
``.syn`` file and makes lookups work on a real page of prose.

Two extraction modes, because the two useful shapes of the data are different:

``translations``
    Read the **English** edition and harvest the translation tables:
    ``dog`` -> ``{"code": "pt", "word": "cao"}``.  Wide coverage, shallow
    entries, and the sense linkage is often a free-text hint rather than an id.

``foreign_entries``
    Read the **target language's** edition and keep the pages whose
    ``lang_code`` is the source language: English words defined *in Portuguese*
    by Portuguese speakers.  Far better prose, far fewer headwords (the whole
    reason this project exists -- the pt edition has ~12.7k English entries).

``definitions``
    Monolingual.  Read an edition and keep the pages it writes about its own
    language, so nothing is translated: the gloss is a definition and the
    ``synonyms`` lists are synonyms.  Same reader as ``foreign_entries`` with
    the equivalence guess turned off, because in one language a short gloss is
    a short definition, not a translation.

Licence: CC BY-SA 4.0 for all Wiktionary text.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

from ..ir import Entry, Pos, Sense, normalise_headword
from .base import (
    SourceError,
    SourceSpec,
    dedupe_preserving_order,
    open_maybe_gzip,
    require_existing,
)

__all__ = ["INFLECTION_TAG_DENYLIST", "POS_MAP", "KaikkiSource"]

POS_MAP: dict[str, Pos] = {
    "noun": Pos.NOUN, "verb": Pos.VERB, "adj": Pos.ADJ, "adv": Pos.ADV,
    "pron": Pos.PRON, "prep": Pos.PREP, "postp": Pos.PREP, "conj": Pos.CONJ,
    "intj": Pos.INTERJ, "det": Pos.DET, "article": Pos.DET, "num": Pos.NUM,
    "particle": Pos.PARTICLE, "prefix": Pos.PREFIX, "suffix": Pos.SUFFIX,
    "infix": Pos.PREFIX, "phrase": Pos.PHRASE, "prep_phrase": Pos.PHRASE,
    "proverb": Pos.PHRASE, "name": Pos.NAME, "abbrev": Pos.NOUN,
    "contraction": Pos.PHRASE,
}

#: Form rows carrying any of these are not inflections of the headword and must
#: not go into the ``.syn`` file: a romanisation pointing at the headword would
#: make unrelated Latin-script text resolve to it.
INFLECTION_TAG_DENYLIST: frozenset[str] = frozenset({
    "romanization", "transliteration", "romanisation", "table-tags",
    "inflection-template", "class", "auxiliary", "error-unrecognized-form",
    "no-gloss", "hyphenation", "rhymes",
})

#: Synonyms shown on one entry. Six is what fits on an e-reader popup above the
#: definition; past that the reader is scrolling to reach the meaning.
MAX_SYNONYMS = 6

#: Rows whose form field is one of these are wiktextract placeholders rather
#: than real forms. The three dash characters are distinct on purpose --
#: wiktextract emits hyphen-minus, en dash and em dash interchangeably here.
_PLACEHOLDER_FORMS = frozenset({
    "-", "\u2013", "\u2014", "?", "no", "none", "",
})


#: Foreign-edition glosses that are cross-references, not meanings. A sense
#: reading "variante de toward" is an inflection pointer that wiktextract did
#: not tag with form_of, and shipping it makes the entry look empty.
_POINTER_GLOSS = re.compile(
    r"^\s*\(?[^)]*\)?\s*(?:"
    r"variante|varia[cç][aã]o|forma|flex[aã]o|plural|singular|feminino|masculino|"
    r"diminutivo|aumentativo|superlativo|comparativo|particípio|gerúndio|"
    r"grafia|abreviatura|sigla|"
    r"variant|alternative form|plural|inflection of|obsolete form|misspelling"
    r")\b.{0,40}\b(?:de|do|da|of)\b",
    re.IGNORECASE,
)

#: True IPA has no ASCII capitals and marks stress with U+02C8, not a quote.
#: wiktextract passes through SAMPA and other ad-hoc notations (``/bI"haInd/``)
#: which render as noise next to real transcriptions.
_NOT_IPA = re.compile(r'["A-Z]')


def _pos(raw: str) -> Pos:
    return POS_MAP.get(raw, Pos.UNKNOWN)


def _split_equivalents(text: str) -> tuple[str, ...]:
    """Split a comma-packed gloss into separate translations.

    A foreign edition often defines an English word as ``"sussurro, cochicho"``.
    Kept whole it is one opaque translation string that no deduplication can
    match against the wordnet's ``("cochicho", "sussurro", ...)``, so the same
    words get printed twice on the same entry.
    """
    parts = [part.strip(" .;") for part in re.split(r"[,;/]", text)]
    return tuple(part for part in parts if part)


class KaikkiSource:
    """Reader for a kaikki.org wiktextract JSONL dump (optionally gzipped)."""

    def __init__(self, spec: SourceSpec, path: Path) -> None:
        self.spec = spec
        self.path = require_existing(Path(path), spec)
        options = spec.options
        self.mode = str(options.get("mode", "translations"))
        if self.mode not in {"translations", "foreign_entries", "definitions"}:
            raise SourceError(f"source {spec.id!r}: unknown kaikki mode {self.mode!r}")
        self._source_lang = str(options.get("source_lang", "en"))
        self._target_lang = str(options.get("target_lang", spec.lang))
        if not self._target_lang:
            raise SourceError(f"source {spec.id!r}: kaikki source needs a target_lang")
        max_senses = options.get("max_senses", 12)
        self.max_senses = int(max_senses) if isinstance(max_senses, int) else 12

    @property
    def source_lang(self) -> str:
        return self._source_lang

    @property
    def target_lang(self) -> str:
        return self._target_lang

    @property
    def license_id(self) -> str:
        return self.spec.license_id or "CC-BY-SA-4.0"

    # -- reading -------------------------------------------------------------

    def _pages(self) -> Iterator[dict[str, Any]]:
        with open_maybe_gzip(self.path) as handle:
            for number, line in enumerate(handle, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError as error:
                    raise SourceError(f"{self.path}:{number}: {error}") from error

    def entries(self) -> Iterator[Entry]:
        if self.mode == "translations":
            yield from self._entries_from_translations()
        else:
            yield from self._entries_from_foreign_pages()

    @property
    def monolingual(self) -> bool:
        return self.mode == "definitions"

    def _translations_for(self, rows: Iterable[Any] | None) -> tuple[str, ...]:
        return dedupe_preserving_order(
            str(row.get("word", "")).strip()
            for row in (rows or ())
            if isinstance(row, dict)
            and row.get("code") == self._target_lang
            and row.get("word")
        )

    def _entries_from_translations(self) -> Iterator[Entry]:
        """Harvest translation tables from the source language's own edition.

        wiktextract attaches translations in two places and the split is not
        even: in the English edition, page-level ``translations`` appear on a
        small minority of pages, while ``senses[].translations`` appear on an
        order of magnitude more. Reading only the page level -- the shape most
        of the documentation shows -- silently discards the great majority of
        the data. So both are read, and sense-level rows are kept attached to
        the sense they belong to, which is strictly better than flattening them:
        it means "bank" gets *margem* under the riverbank sense and *banco*
        under the financial one.
        """
        provenance = (self.spec.provenance(self.license_id),)
        for page in self._pages():
            if page.get("lang_code") != self._source_lang:
                continue
            headword = normalise_headword(page.get("word", ""))
            if not headword:
                continue
            pos = _pos(page.get("pos", ""))

            senses: list[Sense] = []
            for rank, raw in enumerate(page.get("senses", ())[: self.max_senses], start=1):
                translations = self._translations_for(raw.get("translations"))
                if not translations:
                    continue
                glosses = raw.get("glosses") or raw.get("raw_glosses") or ()
                senses.append(
                    Sense(
                        pos=pos,
                        synset=None,
                        translations=translations,
                        gloss=str(glosses[0]).strip() if glosses else "",
                        gloss_lang=self._source_lang,
                        labels=tuple(str(t) for t in raw.get("tags", ()) if t)[:3],
                        provenance=provenance,
                        # Below any wordnet sense: this is enrichment, and it
                        # should not displace a curated sense at the top of a
                        # lookup popup.
                        rank=50 + rank,
                    )
                )

            if not senses:
                # No sense carried translations, so fall back to the page-level
                # table. When senses do carry them, the page-level table is the
                # same material flattened, and adding it would duplicate.
                page_translations = self._translations_for(page.get("translations"))
                if not page_translations:
                    continue
                gloss = ""
                for raw in page.get("senses", ()):
                    glosses = raw.get("glosses") or raw.get("raw_glosses") or ()
                    if glosses:
                        gloss = str(glosses[0])
                        break
                senses.append(
                    Sense(
                        pos=pos,
                        synset=None,
                        translations=page_translations,
                        gloss=gloss,
                        gloss_lang=self._source_lang,
                        provenance=provenance,
                        rank=50,
                    )
                )

            yield Entry(
                headword=headword,
                lang=self._source_lang,
                senses=senses,
                forms=self._forms(page, headword),
                pronunciations=self._pronunciations(page),
            )

    def _entries_from_foreign_pages(self) -> Iterator[Entry]:
        """Pages describing source-language words, glossed in the target language.

        In ``definitions`` mode the two languages are the same, which changes
        one thing: the gloss is never reinterpreted as an equivalent, and the
        page's synonym lists take its place.
        """
        provenance = (self.spec.provenance(self.license_id),)
        for page in self._pages():
            if page.get("lang_code") != self._source_lang:
                continue
            headword = normalise_headword(page.get("word", ""))
            if not headword:
                continue
            pos = _pos(page.get("pos", ""))
            page_synonyms = self._page_synonyms(page) if self.monolingual else {}
            senses: list[Sense] = []
            for rank, raw in enumerate(page.get("senses", ())[: self.max_senses], start=1):
                glosses = raw.get("glosses") or raw.get("raw_glosses") or ()
                if not glosses:
                    continue
                # A "plural of dog" sense is an inflection pointer, not a
                # meaning; it belongs in the .syn file, handled by inflections().
                if raw.get("form_of") or raw.get("alt_of"):
                    continue
                text = str(glosses[0]).strip()
                if not text or _POINTER_GLOSS.match(text):
                    continue
                senses.append(
                    Sense(
                        pos=pos,
                        synset=None,
                        # In this mode the gloss *is* the translation material:
                        # a short gloss is usually a bare equivalent, a long one
                        # is a real definition. Only the short ones are safe to
                        # treat as translations.
                        translations=(
                            self._synonyms(raw, page_synonyms, rank, headword)
                            if self.monolingual
                            else _split_equivalents(text)
                            if _looks_like_a_bare_equivalent(text)
                            else ()
                        ),
                        gloss=text,
                        gloss_lang=self._target_lang,
                        examples=tuple(
                            str(e.get("text", "")).strip()
                            for e in raw.get("examples", ())
                            if e.get("text")
                        )[:3],
                        labels=tuple(str(t) for t in raw.get("tags", ()) if t),
                        provenance=provenance,
                        rank=rank,
                    )
                )
            if not senses:
                continue
            yield Entry(
                headword=headword,
                lang=self._source_lang,
                senses=senses,
                forms=self._forms(page, headword),
                pronunciations=self._pronunciations(page),
            )

    # -- synonyms (monolingual only) -----------------------------------------

    @staticmethod
    def _page_synonyms(page: dict[str, Any]) -> dict[int, list[str]]:
        """Page-level synonym rows, keyed by the 1-based sense they belong to.

        Editions differ on where they put these. The English edition mostly
        attaches them to the sense; the Portuguese edition mostly lists them on
        the page with a ``sense_index`` pointing back. Rows with no index land
        under 0 and are attached to the first sense.
        """
        grouped: dict[int, list[str]] = defaultdict(list)
        for row in page.get("synonyms", ()) or ():
            if not isinstance(row, dict):
                continue
            word = normalise_headword(str(row.get("word", "")))
            if word:
                try:
                    index = int(row.get("sense_index") or 0)
                except (TypeError, ValueError):
                    index = 0
                grouped[index].append(word)
        return grouped

    @staticmethod
    def _synonyms(
        sense: dict[str, Any],
        page_synonyms: dict[int, list[str]],
        rank: int,
        headword: str,
    ) -> tuple[str, ...]:
        words = [
            normalise_headword(str(row.get("word", "")))
            for row in (sense.get("synonyms") or ())
            if isinstance(row, dict)
        ]
        words += page_synonyms.get(rank, [])
        if rank == 1:
            words += page_synonyms.get(0, [])
        return dedupe_preserving_order(w for w in words if w and w != headword)[:MAX_SYNONYMS]

    # -- inflections ---------------------------------------------------------

    def _forms(self, page: dict[str, Any], headword: str) -> set[str]:
        out: set[str] = set()
        for row in page.get("forms", ()):
            tags = {str(t) for t in row.get("tags", ())}
            if tags & INFLECTION_TAG_DENYLIST:
                continue
            form = normalise_headword(str(row.get("form", "")))
            if not form or form.lower() in _PLACEHOLDER_FORMS or form == headword:
                continue
            if len(form.encode("utf-8")) > 255:
                continue
            out.add(form)
        return out

    @staticmethod
    def _pronunciations(page: dict[str, Any]) -> tuple[str, ...]:
        candidates = (
            str(sound["ipa"]).strip() for sound in page.get("sounds", ()) if sound.get("ipa")
        )
        return dedupe_preserving_order(
            ipa for ipa in candidates if ipa and not _NOT_IPA.search(ipa)
        )[:2]

    def inflections(self) -> Iterator[tuple[str, str]]:
        """``(form, lemma)`` pairs harvested from the whole dump.

        Two independent signals, because neither alone is complete:

        * ``forms`` rows on a lemma's own page (``dog`` lists ``dogs``);
        * ``form_of`` senses on an inflected page (``dogs`` says "plural of
          dog"), which catches suppletive forms like *went* that no rule
          generates and that many pages omit from their tables.
        """
        for page in self._pages():
            if page.get("lang_code") != self._source_lang:
                continue
            headword = normalise_headword(page.get("word", ""))
            if not headword:
                continue
            for form in self._forms(page, headword):
                yield form, headword
            for sense in page.get("senses", ()):
                for pointer in list(sense.get("form_of", ())) + list(sense.get("alt_of", ())):
                    lemma = normalise_headword(str(pointer.get("word", "")))
                    if lemma and lemma != headword:
                        yield headword, lemma


def _looks_like_a_bare_equivalent(text: str) -> bool:
    """True when a foreign-edition gloss is really just a translation.

    ``"cão"`` is a translation; ``"animal mamífero da família dos canídeos,
    domesticado pelo homem"`` is a definition.  The distinction matters for the
    "% with a real translation" metric, so it is drawn conservatively: at most
    three words and no sentence punctuation.
    """
    stripped = text.strip().rstrip(".")
    if not stripped or len(stripped) > 60:
        return False
    if any(ch in stripped for ch in ":()[]"):
        return False
    # Comma-separated lists of equivalents are still equivalents; they are split
    # apart by _split_equivalents. Each part must itself be short.
    parts = _split_equivalents(stripped)
    return bool(parts) and all(len(part.split()) <= 3 for part in parts)
