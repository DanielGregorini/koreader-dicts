"""The internal representation every source adapter normalises into.

Three things shape it:

* Senses are anchored to a Princeton WordNet 3.0 synset id ("02084071-n").
  That id is the join key the pivot uses. A sense with no synset -- a
  Wiktionary sense with no wordnet counterpart -- is still stored; it just
  cannot take part in the pivot.
* Licence provenance is recorded per sense, not per dictionary, so the bundle
  licence is decided from the senses actually emitted.
* A tier-1 pair holds around 10^5 entries and 10^6 senses, so every class uses
  slots=True and shares Provenance instances.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass, field
from enum import StrEnum

__all__ = [
    "Dictionary",
    "Entry",
    "Pos",
    "Provenance",
    "Sense",
    "SynsetId",
    "canonical_synset",
    "normalise_headword",
]

#: ``"%08d-%s" % (offset, pos)`` using PWN 3.0 offsets, e.g. ``02084071-n``,
#: with *pos* always one of ``n v a r`` -- see :func:`canonical_synset`.
SynsetId = str


class Pos(StrEnum):
    NOUN = "noun"
    VERB = "verb"
    ADJ = "adj"
    ADV = "adv"
    PRON = "pron"
    PREP = "prep"
    CONJ = "conj"
    INTERJ = "interj"
    DET = "det"
    NUM = "num"
    PARTICLE = "particle"
    PREFIX = "prefix"
    SUFFIX = "suffix"
    PHRASE = "phrase"
    NAME = "name"
    UNKNOWN = "unknown"

    @property
    def label(self) -> str:
        return _POS_LABELS[self]

    @property
    def wordnet_tag(self) -> str | None:
        """The single-letter tag used in PWN/OMW synset ids, if any."""
        return {Pos.NOUN: "n", Pos.VERB: "v", Pos.ADJ: "a", Pos.ADV: "r"}.get(self)

    @staticmethod
    def from_wordnet_tag(tag: str) -> Pos:
        # 's' is an adjective satellite; it is an adjective for display purposes
        # but the tag must be preserved inside the synset id itself.
        return {"n": Pos.NOUN, "v": Pos.VERB, "a": Pos.ADJ, "s": Pos.ADJ, "r": Pos.ADV}.get(tag, Pos.UNKNOWN)


_POS_LABELS: Mapping[Pos, str] = {
    Pos.NOUN: "n.", Pos.VERB: "v.", Pos.ADJ: "adj.", Pos.ADV: "adv.",
    Pos.PRON: "pron.", Pos.PREP: "prep.", Pos.CONJ: "conj.", Pos.INTERJ: "interj.",
    Pos.DET: "det.", Pos.NUM: "num.", Pos.PARTICLE: "part.", Pos.PREFIX: "pref.",
    Pos.SUFFIX: "suf.", Pos.PHRASE: "phr.", Pos.NAME: "prop. n.", Pos.UNKNOWN: "",
}

#: Ordering used when rendering an entry: the parts of speech a reader is most
#: likely to want first.  Stable across runs so output is byte-reproducible.
POS_ORDER: tuple[Pos, ...] = (
    Pos.NOUN, Pos.VERB, Pos.ADJ, Pos.ADV, Pos.PRON, Pos.DET, Pos.NUM,
    Pos.PREP, Pos.CONJ, Pos.INTERJ, Pos.PARTICLE, Pos.PHRASE, Pos.NAME,
    Pos.PREFIX, Pos.SUFFIX, Pos.UNKNOWN,
)


@dataclass(frozen=True, slots=True, order=True)
class Provenance:
    """Where a sense came from and under what terms.

    Instances are shared: an adapter creates one per source and attaches the
    same object to every sense it emits.
    """

    source_id: str
    license_id: str
    #: Credit line the upstream project asks to be shown.
    credit: str = ""
    #: Upstream version/release, recorded so a build is reproducible.
    version: str = ""


@dataclass(slots=True)
class Sense:
    """One meaning of one headword, expressed for the target language."""

    pos: Pos = Pos.UNKNOWN
    #: PWN 3.0 synset id, or None for senses outside the wordnet.
    synset: SynsetId | None = None
    #: Target-language equivalents, best first.  Empty means gloss-only.
    translations: tuple[str, ...] = ()
    #: Definition text.  May be in the source language (a PWN gloss on an
    #: en->pt entry) or the target language (a Portuguese Wiktionary sense).
    gloss: str = ""
    #: BCP-47-ish code for the language *gloss* is written in.
    gloss_lang: str = ""
    #: Usage examples, in whatever language they were sourced in.
    examples: tuple[str, ...] = ()
    #: Register/domain/usage labels: "informal", "botany", "archaic".
    labels: tuple[str, ...] = ()
    provenance: tuple[Provenance, ...] = ()
    #: Lower sorts first within a part of speech.  Sources set this from their
    #: own sense ordering (WordNet sense number, Wiktionary sense position) so
    #: the most common meaning stays on top after merging.
    rank: int = 0
    #: Corpus tag count: how often this sense was actually annotated in a
    #: sense-tagged corpus.  Higher is more common.  Unlike ``rank`` this is
    #: comparable *across* parts of speech, which is what decides whether
    #: "behind" leads with the preposition or with the buttocks.
    frequency: int = 0

    @property
    def has_translation(self) -> bool:
        return bool(self.translations)

    @property
    def license_ids(self) -> frozenset[str]:
        return frozenset(p.license_id for p in self.provenance)

    def merge_key(self) -> tuple[str, str, str]:
        """Identity used to collapse duplicate senses arriving from two sources.

        Synset-anchored senses collapse on the synset; unanchored ones collapse
        on the normalised gloss, which is the best available proxy.
        """
        if self.synset:
            return ("synset", self.synset, "")
        return ("gloss", str(self.pos), " ".join(self.gloss.lower().split())[:160])


@dataclass(slots=True)
class Entry:
    """A headword and everything we know about it."""

    headword: str
    #: Language of *headword* (the source side of the pair).
    lang: str
    senses: list[Sense] = field(default_factory=list)
    #: Inflected forms that should resolve to this entry via the ``.syn`` file.
    #: Never includes the headword itself.
    forms: set[str] = field(default_factory=set)
    #: IPA transcriptions, in order of preference.
    pronunciations: tuple[str, ...] = ()

    @property
    def license_ids(self) -> frozenset[str]:
        out: set[str] = set()
        for sense in self.senses:
            out |= sense.license_ids
        return frozenset(out)

    @property
    def provenance(self) -> frozenset[Provenance]:
        return frozenset(p for sense in self.senses for p in sense.provenance)

    @property
    def translation_count(self) -> int:
        return sum(len(s.translations) for s in self.senses)

    @property
    def has_translation(self) -> bool:
        return any(s.translations for s in self.senses)

    def senses_by_pos(self) -> list[tuple[Pos, list[Sense]]]:
        """Senses grouped and ordered for rendering, most useful first.

        Grouping by part of speech and then always showing nouns first is the
        obvious implementation and it is wrong.  It makes *behind* open with
        the buttocks (a noun tagged once in the corpus) instead of the
        preposition (tagged thirteen times), and *run* open with a baseball
        score instead of the verb.  On a six-inch screen the reader sees the
        first two lines and nothing else, so that is the whole lookup.

        So groups are ordered by the corpus frequency of their best sense, and
        :data:`POS_ORDER` only breaks ties -- which is what happens for the
        many entries with no frequency evidence at all.

        Within a group, senses that actually have a translation come before
        gloss-only ones regardless of frequency.  A bilingual reader who taps a
        word wants the word, and an English definition sitting above the
        Portuguese equivalent wastes the two lines they will actually read.
        """
        buckets: dict[Pos, list[Sense]] = {}
        for sense in self.senses:
            buckets.setdefault(sense.pos, []).append(sense)

        fallback = {pos: index for index, pos in enumerate(POS_ORDER)}

        def sense_key(sense: Sense) -> tuple[int, int, int, str]:
            return (0 if sense.translations else 1, -sense.frequency, sense.rank, sense.gloss)

        def group_key(item: tuple[Pos, list[Sense]]) -> tuple[int, int, str]:
            pos, group = item
            translated = [s.frequency for s in group if s.translations]
            # Rank the group on its best *translated* sense where it has one,
            # so a part of speech the target language cannot express does not
            # win the top of the entry on frequency alone.
            best = max(translated, default=0) or max((s.frequency for s in group), default=0)
            return (-best, fallback.get(pos, len(fallback)), str(pos))

        ordered = [(pos, sorted(group, key=sense_key)) for pos, group in buckets.items()]
        ordered.sort(key=group_key)
        return ordered

    def absorb(self, other: Entry) -> None:
        """Fold *other* into this entry, collapsing duplicate senses.

        Duplicate senses do not overwrite each other: translations are unioned
        (preserving first-seen order, which is the better source's order) and
        provenance accumulates, so the licence set stays honest.
        """
        if other.headword != self.headword:
            raise ValueError(f"cannot absorb {other.headword!r} into {self.headword!r}")
        index = {s.merge_key(): s for s in self.senses}
        for sense in other.senses:
            key = sense.merge_key()
            existing = index.get(key)
            if existing is None:
                self.senses.append(sense)
                index[key] = sense
                continue
            existing.translations = _dedupe(existing.translations, sense.translations)
            existing.examples = _dedupe(existing.examples, sense.examples)
            existing.labels = _dedupe(existing.labels, sense.labels)
            existing.provenance = tuple(sorted(set(existing.provenance) | set(sense.provenance)))
            existing.frequency = max(existing.frequency, sense.frequency)
            if not existing.gloss and sense.gloss:
                existing.gloss, existing.gloss_lang = sense.gloss, sense.gloss_lang
            if existing.pos is Pos.UNKNOWN:
                existing.pos = sense.pos
        self.forms |= other.forms
        self.forms.discard(self.headword)
        self.pronunciations = _dedupe(self.pronunciations, other.pronunciations)


def _dedupe(*groups: Iterable[str]) -> tuple[str, ...]:
    """Concatenate iterables, dropping repeats, preserving first-seen order."""
    seen: dict[str, None] = {}
    for group in groups:
        for item in group:
            if item:
                seen.setdefault(item, None)
    return tuple(seen)


@dataclass(slots=True)
class Dictionary:
    """A complete bilingual dictionary, ready to hand to a writer."""

    source_lang: str
    target_lang: str
    entries: dict[str, Entry] = field(default_factory=dict)
    #: source_id -> credit line, for the ATTRIBUTION file.
    credits: dict[str, str] = field(default_factory=dict)

    @property
    def pair(self) -> str:
        return f"{self.source_lang}-{self.target_lang}"

    def __len__(self) -> int:
        return len(self.entries)

    def __iter__(self) -> Iterator[Entry]:
        return iter(self.entries.values())

    def add(self, entry: Entry) -> None:
        existing = self.entries.get(entry.headword)
        if existing is None:
            self.entries[entry.headword] = entry
        else:
            existing.absorb(entry)

    def extend(self, entries: Iterable[Entry]) -> None:
        for entry in entries:
            self.add(entry)

    @property
    def license_ids(self) -> frozenset[str]:
        out: set[str] = set()
        for entry in self.entries.values():
            out |= entry.license_ids
        return frozenset(out)

    @property
    def form_count(self) -> int:
        """Number of distinct inflected forms across the dictionary."""
        return len({form for e in self.entries.values() for form in e.forms})

    def drop_licenses(self, license_ids: Iterable[str]) -> int:
        """Remove every sense carrying one of *license_ids*.

        This is how an incompatible source (WOLF in a CC BY-SA bundle) is
        excluded without rebuilding the whole pipeline.  Returns the number of
        senses dropped; entries left with no senses are removed.
        """
        banned = frozenset(license_ids)
        dropped = 0
        for headword in list(self.entries):
            entry = self.entries[headword]
            kept = [s for s in entry.senses if not (s.license_ids & banned)]
            dropped += len(entry.senses) - len(kept)
            if kept:
                entry.senses = kept
            else:
                del self.entries[headword]
        return dropped


def canonical_synset(offset: str, pos_tag: str) -> SynsetId:
    """Build the canonical synset id, folding adjective satellites into ``a``.

    Princeton WordNet distinguishes head adjectives (``ss_type`` ``a``) from
    satellites (``s``), but the Open Multilingual Wordnet 1.4 release writes
    *both* as ``-a``: the Portuguese lexicon has ``omw-pt-00003553-a`` for a
    synset whose ``data.adj`` line says ``s``.  Keeping the distinction would
    mean every satellite -- roughly 18k synsets, a large share of all adjectives
    -- silently failing to pivot.

    Folding is lossless: the offset is a byte offset into ``data.adj``, so it is
    already unique across both types and no two synsets can collide.
    """
    return f"{offset}-{'a' if pos_tag == 's' else pos_tag}"


#: Combining acute and grave after a Cyrillic letter. In Russian, Ukrainian and
#: Bulgarian these mark stress; no running text carries them, so a headword or
#: inflected form that keeps them can never be looked up. Restricted to Cyrillic
#: on purpose: after a Latin letter the same code points are part of the letter.
_CYRILLIC_STRESS = re.compile(r"(?<=[\u0400-\u052f])[\u0300\u0301]")


def normalise_headword(word: str) -> str:
    """Canonical form of a headword: collapse whitespace, strip edges.

    Deliberately does *not* case-fold or strip diacritics.  StarDict lookup is
    already ASCII-case-insensitive via the collation, and folding here would
    merge distinct headwords ("Polish"/"polish", "resume"/"résumé").  Cyrillic
    stress marks are the one exception, and they are not diacritics.
    """
    return " ".join(_CYRILLIC_STRESS.sub("", word).split())
