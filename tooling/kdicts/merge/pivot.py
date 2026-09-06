"""The synset pivot: generate any pair from two wordnets and no bilingual data.

Every wordnet in the Open Multilingual Wordnet keys its lemmas against the same
Princeton WordNet 3.0 synset ids.  So if language A is mapped and language B is
mapped, A->B exists already -- it just has not been written down::

    "wield" --(PWN index)--> 01095899-v --(OMW por)--> "empunhar", "manejar"

OMW 1.4 maps around 22 languages, so one pipeline covers 462 directed pairs.

Direct bilingual material -- Wiktionary translation tables and the like -- is
layered on top afterwards by :mod:`kdicts.merge.enrich`. The pivot is always
the primary mechanism.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Protocol

from ..ir import Dictionary, Entry, Pos, Provenance, Sense, SynsetId, normalise_headword

__all__ = ["PivotConfig", "PivotStats", "build_pivot", "synset_to_lemmas"]


class _HasLemmas(Protocol):
    spec: object

    @property
    def lang(self) -> str: ...

    @property
    def license_id(self) -> str: ...

    def lemmas(self) -> Iterable[object]: ...

    def synsets(self) -> Iterable[object]: ...


@dataclass(slots=True)
class PivotConfig:
    """Knobs that change what the pivot emits, not how it works."""

    #: Keep senses that have a gloss but no target-language lemma.  For en->pt
    #: these are entries where WordNet knows the concept and OpenWN-PT has no
    #: Portuguese word for it: still useful to a reader, but they must be
    #: counted separately in the metrics, never sold as translations.
    keep_gloss_only: bool = True
    #: Preference order of languages for the definition text shown to the
    #: reader.  Target language first: a Portuguese reader wants a Portuguese
    #: definition, and only falls back to the English gloss.
    gloss_langs: tuple[str, ...] = ()
    #: Cap on target-language equivalents per sense. Long lists of near
    #: synonyms are noise on a six-inch screen: eight Portuguese words for
    #: "however" tell a reader less than three do.
    max_translations: int = 5
    #: Drop senses ranked below this in the source wordnet. 0 means keep all.
    max_senses_per_entry: int = 0


@dataclass(slots=True)
class PivotStats:
    source_lemmas: int = 0
    target_lemmas: int = 0
    shared_synsets: int = 0
    entries: int = 0
    senses_with_translation: int = 0
    senses_gloss_only: int = 0
    senses_dropped_empty: int = 0
    licenses: set[str] = field(default_factory=set)


def collapsed_multiword_forms(lemmas: Iterable[str]) -> frozenset[str]:
    """Space-stripped forms of every multi-word lemma in a lexicon.

    Used to recognise run-together corruptions; see
    :func:`drop_malformed_variants`.
    """
    return frozenset(
        lemma.replace(" ", "").lower() for lemma in lemmas if " " in lemma
    )


def drop_malformed_variants(lemmas: list[str], collapsed: frozenset[str]) -> list[str]:
    """Remove run-together corruptions of multi-word lemmas.

    Several OMW lexicons contain lemmas whose spaces were lost upstream:
    OpenWN-PT lists ``adespeitode`` and ``apesarde`` for *however*. Printed
    beside the real forms they read as typos and make the whole entry look
    untrustworthy -- a disproportionate cost for the characters they occupy.

    *collapsed* must be built from the **whole lexicon**, not one synset: the
    corrupted form and the correct one frequently do not co-occur, so
    ``adespeitode`` is only recognisable because ``a despeito de`` exists
    somewhere else in the same wordnet.

    Multi-word lemmas are never dropped, and a single-word lemma survives
    unless the lexicon separately spells it with spaces -- so a genuine
    one-word synonym cannot be caught by this.
    """
    return [
        lemma
        for lemma in lemmas
        if " " in lemma or lemma.replace(" ", "").lower() not in collapsed
    ]


def synset_to_lemmas(source: object) -> dict[SynsetId, list[str]]:
    """``synset -> ordered lemmas`` for the *target* side of a pivot.

    Prefers ``synset_members()`` where the adapter offers it (WordNet reads it
    straight from the data files, which is both faster and complete for
    satellite adjectives), and otherwise groups the ranked ``lemmas()`` stream.
    """
    members = getattr(source, "synset_members", None)
    if callable(members):
        grouped: dict[SynsetId, list[str]] = defaultdict(list)
        for synset, lemma in members():
            lemma = normalise_headword(lemma)
            if lemma and lemma not in grouped[synset]:
                grouped[synset].append(lemma)
        collapsed = collapsed_multiword_forms(
            lemma for items in grouped.values() for lemma in items
        )
        return {
            synset: drop_malformed_variants(items, collapsed)
            for synset, items in grouped.items()
        }

    ranked: dict[SynsetId, list[tuple[int, str]]] = defaultdict(list)
    for record in source.lemmas():  # type: ignore[attr-defined]
        lemma = normalise_headword(record.lemma)
        if lemma:
            ranked[record.synset].append((record.rank, lemma))
    collapsed = collapsed_multiword_forms(
        lemma for items in ranked.values() for _rank, lemma in items
    )
    out: dict[SynsetId, list[str]] = {}
    for synset, items in ranked.items():
        seen: dict[str, None] = {}
        for _rank, lemma in sorted(items):
            seen.setdefault(lemma, None)
        out[synset] = drop_malformed_variants(list(seen), collapsed)
    return out


def _collect_glosses(
    providers: Sequence[tuple[str, object]],
    preference: Sequence[str],
) -> dict[SynsetId, tuple[str, str, tuple[str, ...], Pos, str]]:
    """``synset -> (gloss, gloss_lang, examples, pos, source_id)``.

    Providers are consulted in *preference* order, so a target-language
    definition wins over an English one; a provider still fills in examples and
    part of speech for a synset whose gloss came from someone else.
    """
    order = {lang: index for index, lang in enumerate(preference)}
    ranked = sorted(providers, key=lambda item: order.get(item[0], len(order)))
    out: dict[SynsetId, tuple[str, str, tuple[str, ...], Pos, str]] = {}
    for lang, provider in ranked:
        source_id = getattr(getattr(provider, "spec", None), "id", lang)
        for record in provider.synsets():  # type: ignore[attr-defined]
            existing = out.get(record.synset)
            if existing is None:
                out[record.synset] = (
                    record.gloss, lang, record.examples, record.pos, source_id
                )
            elif not existing[0] and record.gloss:
                out[record.synset] = (record.gloss, lang, existing[2] or record.examples,
                                      existing[3], source_id)
            elif not existing[2] and record.examples:
                out[record.synset] = (existing[0], existing[1], record.examples,
                                      existing[3], existing[4])
    return out


def build_pivot(
    source_side: object,
    target_side: object,
    *,
    gloss_providers: Sequence[tuple[str, object]] = (),
    config: PivotConfig | None = None,
) -> tuple[Dictionary, PivotStats]:
    """Generate ``source_side.lang -> target_side.lang`` through shared synsets.

    Neither side needs to know the other exists.  Reversing a pair (Tier 4) is
    the same call with the arguments swapped; a pair with no English on either
    side (Tier 3, es->pt) is the same call with two OMW wordnets.
    """
    config = config or PivotConfig()
    stats = PivotStats()
    source_lang = source_side.lang  # type: ignore[attr-defined]
    target_lang = target_side.lang  # type: ignore[attr-defined]
    dictionary = Dictionary(source_lang=source_lang, target_lang=target_lang)

    preference = config.gloss_langs or (target_lang, source_lang, "en")
    glosses = _collect_glosses(list(gloss_providers), preference)
    target_lemmas = synset_to_lemmas(target_side)
    stats.target_lemmas = sum(len(v) for v in target_lemmas.values())

    source_provenance: Provenance = source_side.spec.provenance(source_side.license_id)  # type: ignore[attr-defined]
    target_provenance: Provenance = target_side.spec.provenance(target_side.license_id)  # type: ignore[attr-defined]
    gloss_provenance: dict[str, Provenance] = {}
    for _lang, provider in gloss_providers:
        spec = provider.spec  # type: ignore[attr-defined]
        gloss_provenance[spec.id] = spec.provenance(provider.license_id)  # type: ignore[attr-defined]

    # lemma -> [(rank, synset, frequency)], built in one pass over the source
    # side.  The frequency travels with the sense so the renderer can order
    # parts of speech by real usage instead of a fixed noun-first convention.
    by_lemma: dict[str, list[tuple[int, SynsetId, int]]] = defaultdict(list)
    for record in source_side.lemmas():  # type: ignore[attr-defined]
        lemma = normalise_headword(record.lemma)
        if lemma:
            by_lemma[lemma].append((record.rank, record.synset, record.frequency))
    stats.source_lemmas = len(by_lemma)
    stats.shared_synsets = len(
        {synset for pairs in by_lemma.values() for _, synset, _ in pairs} & set(target_lemmas)
    )

    for lemma, pairs in by_lemma.items():
        senses: list[Sense] = []
        seen_synsets: set[SynsetId] = set()
        for rank, synset, frequency in sorted(pairs):
            if synset in seen_synsets:
                continue
            seen_synsets.add(synset)
            if config.max_senses_per_entry and len(senses) >= config.max_senses_per_entry:
                break

            translations = tuple(target_lemmas.get(synset, ())[: config.max_translations])
            gloss, gloss_lang, examples, pos, gloss_source = glosses.get(
                synset, ("", "", (), Pos.from_wordnet_tag(synset[-1]), "")
            )
            if not translations and not (config.keep_gloss_only and gloss):
                stats.senses_dropped_empty += 1
                continue

            provenance = [source_provenance]
            if translations:
                provenance.append(target_provenance)
                stats.senses_with_translation += 1
            else:
                stats.senses_gloss_only += 1
            if gloss and gloss_source in gloss_provenance:
                provenance.append(gloss_provenance[gloss_source])

            senses.append(
                Sense(
                    pos=pos or Pos.from_wordnet_tag(synset[-1]),
                    synset=synset,
                    translations=translations,
                    gloss=gloss,
                    gloss_lang=gloss_lang,
                    examples=examples,
                    provenance=tuple(sorted(set(provenance))),
                    rank=rank,
                    frequency=frequency,
                )
            )

        if senses:
            dictionary.add(Entry(headword=lemma, lang=source_lang, senses=senses))

    stats.entries = len(dictionary)
    stats.licenses = set(dictionary.license_ids)
    return dictionary, stats
