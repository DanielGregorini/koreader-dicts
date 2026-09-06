from __future__ import annotations

import random

import pytest

#: A deliberately nasty headword sample: ASCII case pairs that exercise the
#: strcmp tiebreak, Latin-1 supplement and combining sequences that must sort by
#: raw byte value, non-Latin scripts, RTL, punctuation, digits, and multi-word
#: phrases with the spaces that normalisation has to survive.
NASTY_WORDS: list[str] = [
    "a", "A", "aa", "Aa", "aA", "AA", "ab", "Ab", "AB", "z", "Z", "zz",
    "apple", "Apple", "APPLE", "apple pie", "apple-pie", "apple's",
    "Ångström", "ångström", "ação", "acao", "açúcar", "cafe", "café", "Café",
    "über", "Über", "ünique", "æther", "Æther", "œuvre", "ß", "straße",
    "naïve", "naive", "résumé", "resume", "Resume", "RESUME",
    "日本語", "日本", "中文", "中国", "한국어", "ひらがな",
    "Ελλάδα", "ελλάδα", "Москва", "москва", "мир",
    "العربية", "عربي", "كتاب", "עברית",
    "ก", "กา", "ไทย",
    "3D", "3-D", "42", "1st", "0", "007",
    "-", "--", "'", "\"", "(", ")", ".", "...", "&", "@", "#",
    "e.g.", "i.e.", "etc.", "Dr.", "St. John",
    "co-op", "co op", "coop", "COOP",
    "ﬁle", "ﬀ",
    "á", "á",  # combining acute vs precomposed: distinct byte strings
    "zü", "zü",
]


@pytest.fixture()
def nasty_words() -> list[str]:
    return list(NASTY_WORDS)


@pytest.fixture()
def rng() -> random.Random:
    return random.Random(20240601)


def random_word(rng: random.Random) -> str:
    """A random headword drawn from ranges that stress the comparator."""
    alphabets = [
        "abcdefghijklmnopqrstuvwxyz",
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
        "0123456789",
        " -'.",
        "àáâãäåçèéêëìíîïñòóôõöùúûüýÿ",
        "ÀÁÂÃÄÅÇÈÉÊËÌÍÎÏÑÒÓÔÕÖÙÚÛÜÝ",
        "αβγδεζηθικλμνξοπρστυφχψω",
        "абвгдежзийклмнопрстуфхцчшщыэюя",
        "日本語中文漢字学校時間",
        "ابتثجحخدذرزسشصضطظعغ",
    ]
    length = rng.randint(1, 9)
    pool = "".join(rng.choice(alphabets) for _ in range(2))
    word = "".join(rng.choice(pool) for _ in range(length))
    return word.strip() or "x"
