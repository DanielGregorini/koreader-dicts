"""Inflected forms for the ``.syn`` file.

The ``.syn`` file maps an inflected form to a headword. A reader taps
*wielded* in a novel; without a syn entry the lookup fails, because the
headword is *wield*.

Three sources of forms, in descending order of trustworthiness:

1. **WordNet exception files** (``noun.exc``, ``verb.exc``, ``adj.exc``,
   ``adv.exc``).  Hand-curated irregulars: *went -> go*, *geese -> goose*.
   These cannot be derived by rule.
2. **Wiktionary form tables**, via :meth:`kdicts.sources.kaikki.KaikkiSource.inflections`.
3. **Regular rules**, below, as the backstop for the long tail of headwords
   neither of the above covers.

The rules over-generate slightly. A spurious form costs a few bytes and is
only ever hit by selecting a string that is not a word; a missing form costs a
failed lookup mid-book.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

from ..ir import Pos

__all__ = ["EXCEPTION_FILES", "english_forms", "wordnet_exceptions"]

EXCEPTION_FILES: dict[str, Pos] = {
    "noun.exc": Pos.NOUN,
    "verb.exc": Pos.VERB,
    "adj.exc": Pos.ADJ,
    "adv.exc": Pos.ADV,
}

_VOWELS = "aeiou"
_SIBILANT = re.compile(r"(s|x|z|ch|sh)$")
_CONSONANT_Y = re.compile(r"[^aeiou]y$")
_CVC = re.compile(r"[^aeiou][aeiou][^aeiouwxy]$")
_VOWEL_GROUP = re.compile(r"[aeiouy]+")


def _doubles_final_consonant(word: str) -> bool:
    """Rough English final-consonant doubling test.

    Doubling needs a stressed final syllable, which we cannot detect, so we
    approximate it with "monosyllabic": *stop -> stopped* but not
    *basic -> basiccer*. Polysyllables that really do double (*refer ->
    referred*) are missed here and picked up from Wiktionary's form tables.
    """
    return bool(_CVC.search(word)) and len(_VOWEL_GROUP.findall(word)) == 1


def _plural(word: str) -> set[str]:
    if _SIBILANT.search(word):
        return {word + "es"}
    if _CONSONANT_Y.search(word):
        return {word[:-1] + "ies"}
    if word.endswith("fe"):
        return {word + "s", word[:-2] + "ves"}
    if word.endswith("f"):
        return {word + "s", word[:-1] + "ves"}
    if word.endswith("o"):
        return {word + "s", word + "es"}
    return {word + "s"}


def _third_person(word: str) -> set[str]:
    return _plural(word)


def _past_and_participle(word: str) -> set[str]:
    if word.endswith("e"):
        return {word + "d"}
    if _CONSONANT_Y.search(word):
        return {word[:-1] + "ied"}
    if _doubles_final_consonant(word):
        # stop -> stopped. Only for monosyllables and stressed finals, which we
        # cannot detect, so emit both and let the spurious one sit unused.
        return {word + word[-1] + "ed", word + "ed"}
    return {word + "ed"}


def _gerund(word: str) -> set[str]:
    if word.endswith("ie"):
        return {word[:-2] + "ying"}
    if word.endswith("e") and not word.endswith(("ee", "oe", "ye")):
        return {word[:-1] + "ing"}
    if _doubles_final_consonant(word):
        return {word + word[-1] + "ing", word + "ing"}
    return {word + "ing"}


def _comparatives(word: str) -> set[str]:
    if word.endswith("e"):
        stem = word[:-1]
    elif _CONSONANT_Y.search(word):
        stem = word[:-1] + "i"
    elif _doubles_final_consonant(word):
        stem = word + word[-1]
    else:
        stem = word
    return {stem + "er", stem + "est"}


def _adverb(word: str) -> set[str]:
    if _CONSONANT_Y.search(word):
        return {word[:-1] + "ily"}       # happy -> happily
    if word.endswith("ic"):
        return {word + "ally"}           # basic -> basically
    if word.endswith("le") and not word.endswith(("ale", "ile", "ole")):
        return {word[:-1] + "y"}         # simple -> simply
    if word.endswith("ll"):
        return {word + "y"}              # full -> fully
    return {word + "ly"}


def english_forms(lemma: str, pos: Pos) -> set[str]:
    """Regular English inflections of *lemma* for *pos*.

    Multi-word headwords inflect on their first word (*take off* ->
    *takes off*), which is where the overwhelming majority of real lookups on
    phrasal entries land.
    """
    lemma = lemma.strip()
    if not lemma or not lemma[0].isalpha():
        return set()

    head, _, tail = lemma.partition(" ")
    if tail:
        return {f"{form} {tail}" for form in english_forms(head, pos)}

    lowered = lemma.lower()
    if pos is Pos.NOUN:
        forms = _plural(lowered)
    elif pos is Pos.VERB:
        forms = _third_person(lowered) | _past_and_participle(lowered) | _gerund(lowered)
    elif pos in (Pos.ADJ, Pos.ADV):
        forms = _comparatives(lowered)
        if pos is Pos.ADJ:
            forms |= _adverb(lowered)
    else:
        return set()

    forms.discard(lowered)
    forms.discard(lemma)
    return {f for f in forms if f and len(f.encode("utf-8")) <= 255}


def wordnet_exceptions(dict_root: Path) -> Iterator[tuple[str, str]]:
    """``(form, lemma)`` pairs from a WNdb ``dict/`` directory's ``*.exc`` files.

    Each line is whitespace-separated: the inflected form first, then one or
    more lemmas it can belong to (*axes -> axis, axe*).
    """
    root = Path(dict_root)
    for filename in EXCEPTION_FILES:
        path = root / filename
        if not path.exists():
            continue
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                parts = line.split()
                if len(parts) < 2:
                    continue
                form = parts[0].replace("_", " ")
                for lemma in parts[1:]:
                    yield form, lemma.replace("_", " ")
