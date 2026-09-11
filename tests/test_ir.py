"""Headword and translation normalisation: what is tapped versus what is shown."""

from __future__ import annotations

from kdicts.ir import normalise_headword, normalise_translation


def test_headwords_lose_the_marks_running_text_never_carries():
    assert normalise_headword("соба́ки") == "собаки"
    assert normalise_headword("كَلْب") == "كلب"
    assert normalise_headword("كِيْلُو مِتْر") == "كيلو متر"


def test_headwords_keep_letter_diacritics_and_case():
    assert normalise_headword("résumé") == "résumé"
    assert normalise_headword("Ελλάδα") == "Ελλάδα"
    assert normalise_headword("Polish") == "Polish"
    assert normalise_headword("  a   b ") == "a b"


def test_translations_keep_their_marks():
    assert normalise_translation("كَلْب") == "كَلْب"
    assert normalise_translation("соба́ка  ") == "соба́ка"
