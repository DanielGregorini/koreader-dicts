"""The sort order of a StarDict index is part of the file format.

If these fail, generated dictionaries lose lookups silently on device.
"""

from __future__ import annotations

import functools

import pytest
from conftest import random_word
from kdicts.collation import ascii_fold, is_sorted, sort_headwords, stardict_strcmp
from kdicts.verify.stardict_reader import g_ascii_strcasecmp
from kdicts.verify.stardict_reader import stardict_strcmp as reference_strcmp


def test_ascii_fold_touches_only_ascii_uppercase():
    assert ascii_fold(b"ABCxyz") == b"abcxyz"
    # Latin-1 supplement: g_ascii_tolower must leave these alone.
    assert ascii_fold("ÀÉÜ".encode()) == "ÀÉÜ".encode()
    assert ascii_fold("Ω".encode()) == "Ω".encode()
    assert ascii_fold(bytes(range(0x80, 0x100))) == bytes(range(0x80, 0x100))
    # Every byte outside A-Z is an identity mapping.
    for byte in range(256):
        expected = byte + 0x20 if 0x41 <= byte <= 0x5A else byte
        assert ascii_fold(bytes([byte])) == bytes([expected])


def test_bytes_above_7f_compare_as_unsigned():
    # The classic signed-char bug: 0xC3 must sort *after* 'z' (0x7A), not before.
    assert stardict_strcmp("é".encode(), b"z") > 0
    assert stardict_strcmp(b"z", "é".encode()) < 0


def test_case_insensitive_primary_exact_tiebreak():
    # Equal under case folding, so the strcmp tiebreak decides, and uppercase
    # 'A' (0x41) sorts before lowercase 'a' (0x61).
    assert g_ascii_strcasecmp(b"Apple", b"apple") == 0
    assert stardict_strcmp(b"Apple", b"apple") < 0
    # But case folding still outranks the tiebreak: "apple" < "Apples".
    assert stardict_strcmp(b"apple", b"Apples") < 0


def test_shorter_prefix_sorts_first():
    assert stardict_strcmp(b"app", b"apple") < 0
    assert stardict_strcmp(b"apple", b"app") > 0
    assert stardict_strcmp(b"apple", b"apple") == 0


@pytest.mark.parametrize("count", [400])
def test_sort_key_matches_the_c_comparator(rng, count):
    """The writer's sort key must agree with the transcribed C comparator.

    The key is an optimisation (tuple compare instead of a Python-level cmp);
    this is the proof that the optimisation is faithful.
    """
    words = [random_word(rng).encode() for _ in range(count)]
    by_key = sort_headwords(words)
    by_cmp = sorted(words, key=functools.cmp_to_key(reference_strcmp))
    assert by_key == by_cmp


def test_sort_key_matches_the_c_comparator_on_nasty_words(nasty_words):
    words = [word.encode() for word in nasty_words]
    assert sort_headwords(words) == sorted(words, key=functools.cmp_to_key(reference_strcmp))


def test_pairwise_agreement_with_reference(nasty_words):
    words = [word.encode() for word in nasty_words]
    for a in words:
        for b in words:
            ours = stardict_strcmp(a, b)
            theirs = reference_strcmp(a, b)
            assert (ours < 0) == (theirs < 0), (a, b, ours, theirs)
            assert (ours > 0) == (theirs > 0), (a, b, ours, theirs)


def test_is_sorted():
    assert is_sorted([b"Apple", b"apple", b"banana"])
    assert not is_sorted([b"apple", b"Apple"])
    assert is_sorted([])
