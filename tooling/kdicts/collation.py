"""StarDict index collation.

A StarDict ``.idx`` (and ``.syn``) file is read by binary search, so the on-disk
order is part of the file format. If it is wrong, lookups fail for a fraction of
the headwords even though the entries are present in the file.

The order is defined by StarDict's ``stardict_strcmp``::

    static inline gint stardict_strcmp(const gchar *s1, const gchar *s2) {
        gint a = g_ascii_strcasecmp(s1, s2);
        return (a == 0) ? strcmp(s1, s2) : a;
    }

and glib's ``g_ascii_strcasecmp``::

    while (*s1 && *s2) {
        c1 = (gint)(guchar) TOLOWER(*s1);
        c2 = (gint)(guchar) TOLOWER(*s2);
        if (c1 != c2) return c1 - c2;
        s1++; s2++;
    }
    return ((gint)(guchar) *s1) - ((gint)(guchar) *s2);

Two properties of that comparator:

1. ``TOLOWER`` is ASCII only. Bytes >= 0x80 are left alone, so "Ä" and "ä" are
   not equal and UTF-8 sequences compare as raw bytes. Using :meth:`str.lower`,
   :func:`locale.strxfrm` or :func:`unicodedata.normalize` here is a bug.
2. Comparison is on unsigned bytes, so 0xC3 sorts after 0x7A.

KOReader looks words up through sdcv, which uses this same comparator. This
module is the only place output ordering is defined.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import TypeVar

__all__ = [
    "ascii_fold",
    "collation_key",
    "is_sorted",
    "sort_headwords",
    "stardict_strcmp",
]

# Lowercases A-Z and leaves every other byte, including the whole >= 0x80
# range, untouched. Mirrors glib's g_ascii_tolower. Built explicitly rather
# than with bytes.lower() so the ASCII-only rule stays visible.
_ASCII_FOLD = bytes(
    b + 0x20 if 0x41 <= b <= 0x5A else b  # 'A'..'Z' -> 'a'..'z'
    for b in range(256)
)

_T = TypeVar("_T")


def ascii_fold(word: bytes) -> bytes:
    """Lowercase ASCII A-Z only, byte for byte. Bytes >= 0x80 are untouched."""
    return word.translate(_ASCII_FOLD)


def collation_key(word: bytes) -> tuple[bytes, bytes]:
    """Sort key equivalent to ``stardict_strcmp``.

    Python compares bytes on unsigned values, shorter prefix first, which is
    what the C loop computes once the NUL terminator is accounted for
    (headwords cannot contain NUL). Folded form first, raw form second,
    reproduces the g_ascii_strcasecmp / strcmp tiebreak.
    """
    return (word.translate(_ASCII_FOLD), word)


def stardict_strcmp(a: bytes, b: bytes) -> int:
    """Three-way comparison matching StarDict's ``stardict_strcmp``."""
    ka, kb = collation_key(a), collation_key(b)
    if ka < kb:
        return -1
    if ka > kb:
        return 1
    return 0


def sort_headwords(words: Iterable[bytes]) -> list[bytes]:
    """Sort raw headword bytes into StarDict index order."""
    return sorted(words, key=collation_key)


def is_sorted(words: Iterable[bytes]) -> bool:
    """True when *words* are already in StarDict index order (ties allowed)."""
    previous: tuple[bytes, bytes] | None = None
    for word in words:
        key = collation_key(word)
        if previous is not None and key < previous:
            return False
        previous = key
    return True
