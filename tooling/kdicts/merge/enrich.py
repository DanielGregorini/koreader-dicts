"""Lay direct bilingual material over a pivot-generated dictionary.

The pivot inherits the wordnets' blind spots: no slang, no idiom, nothing
coined after the wordnet froze, and no inflected forms. Direct bilingual
sources fill those gaps.

Enrichment never replaces a pivot sense. :meth:`kdicts.ir.Entry.absorb` unions
the translations and accumulates provenance, so a sense that picked up a
Wiktionary translation also carries the Wiktionary licence and the bundler
sees it.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from ..ir import Dictionary, Entry

__all__ = ["EnrichStats", "attach_inflections", "enrich"]


@dataclass(slots=True)
class EnrichStats:
    entries_seen: int = 0
    entries_added: int = 0
    entries_extended: int = 0
    senses_added: int = 0
    forms_added: int = 0


def enrich(
    dictionary: Dictionary,
    entries: Iterable[Entry],
    *,
    add_new_headwords: bool = True,
) -> EnrichStats:
    """Fold *entries* into *dictionary*.

    :param add_new_headwords: when False, only headwords the pivot already
        produced are touched.  Useful for a source we trust to improve an entry
        but not to define the dictionary's scope.
    """
    stats = EnrichStats()
    for entry in entries:
        stats.entries_seen += 1
        existing = dictionary.entries.get(entry.headword)
        # A headword the pivot did not produce: add it whole, or skip it.
        if existing is None:
            if not add_new_headwords:
                continue
            dictionary.entries[entry.headword] = entry
            stats.entries_added += 1
            stats.senses_added += len(entry.senses)
            stats.forms_added += len(entry.forms)
            continue
        # Already present: merge into it. absorb() unions the translations and
        # keeps both sources' provenance, which the licence bundler reads.
        before_senses, before_forms = len(existing.senses), len(existing.forms)
        existing.absorb(entry)
        stats.entries_extended += 1
        stats.senses_added += len(existing.senses) - before_senses
        stats.forms_added += len(existing.forms) - before_forms
    return stats


def attach_inflections(
    dictionary: Dictionary,
    pairs: Iterable[tuple[str, str]],
) -> int:
    """Attach ``(form, lemma)`` pairs to their entries.

    Forms whose lemma is not a headword are dropped here rather than in the
    writer, so the count reported to the metrics is the number that will
    actually reach the ``.syn`` file.
    """
    added = 0
    for form, lemma in pairs:
        entry = dictionary.entries.get(lemma)
        # No headword to hang the form on, or the form is the headword itself.
        if entry is None or not form or form == lemma:
            continue
        if form not in entry.forms:
            entry.forms.add(form)
            added += 1
    return added
