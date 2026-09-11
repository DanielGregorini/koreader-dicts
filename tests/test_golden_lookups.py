"""Words as they appear on a page, looked up in the dictionaries actually built.

Every other test here runs on miniature fixtures. This one runs on the real
output under dictionaries/ when it exists, and is skipped when it does not, so
it can catch the class of bug the fixtures cannot: data that is well-formed,
verifiable, and useless -- an inflection index nobody can reach, a placeholder
lemma shipped as a translation.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from kdicts.verify.stardict_reader import StarDictReader

DICTIONARIES = Path(__file__).resolve().parents[1] / "dictionaries"

# (pair, word exactly as a reader would tap it, text the entry must contain)
GOLDEN = [
    ("en-pt", "wielded", "manejar"),
    ("en-pt", "went", "change location"),
    ("en-it", "geese", "oca"),
    ("en-it", "go", "spostarsi"),
    ("en-en", "geese", "web-footed"),
    ("en-en", "run", "move fast"),
    ("es-pt", "patata", "batata"),
    ("es-es", "corrieron", "prisa"),
    ("it-en", "corsero", "run"),
    ("it-it", "corsero", "velocemente"),
    ("pt-pt", "correram", "mover-se com rapidez"),
    ("pt-en", "cachorro", "dog"),
    ("pl-en", "psa", "dog"),
    ("ru-en", "собаки", "dog"),
    ("ru-ru", "книге", "носитель информации"),
    ("fr-fr", "courut", "Se déplacer rapidement"),
    ("zh-zh", "狗", "犬"),
    ("es-en", "perros", "dog"),
    ("ja-en", "走った", "run"),
    ("ja-ja", "犬", "いぬ"),
    ("en-ja", "wielded", "さばく"),
    ("cs-cs", "psi", "psovitá šelma"),
    ("el-el", "βιβλία", "φύλλα χαρτιού"),
    ("ko-ko", "책", "종이 다발"),
    ("de-en", "Hunde", "dog"),
    ("nl-en", "honden", "dog"),
    ("nl-nl", "liepen", "stappen"),
    ("en-nl", "geese", "gans"),
    ("fi-en", "juoksivat", "run"),
    ("de-de", "Hunde", "Haustier"),
    ("ar-en", "كلب", "dog"),
    ("ar-en", "ذهبت", "go"),
    ("ar-ar", "بيت", "مَنْزِل"),
]

# Things that must never appear in a rendered entry.
FORBIDDEN = [
    ("en-it", "go", "PSEUDOGAP"),
    ("en-it", "dog", "GAP!"),
]


def _directory(pair: str) -> Path:
    directory = DICTIONARIES / pair / pair
    if not (directory / f"{pair}.ifo").exists():
        pytest.skip(f"{pair} is not built")
    return directory


@pytest.mark.parametrize(("pair", "word", "expected"), GOLDEN)
def test_a_real_word_resolves_to_the_right_entry(pair, word, expected):
    with StarDictReader(_directory(pair)) as reader:
        found = reader.lookup(word)
    assert found, f"{pair}: {word!r} not found"
    assert expected in found[0], f"{pair}: {word!r} resolved, but not to an entry mentioning {expected!r}"


@pytest.mark.parametrize(("pair", "word", "forbidden"), FORBIDDEN)
def test_placeholders_never_reach_an_entry(pair, word, forbidden):
    with StarDictReader(_directory(pair)) as reader:
        found = reader.lookup(word)
    assert found and forbidden not in found[0]


def test_the_dutch_goose_leads_with_the_bird():
    # Open Dutch WordNet has no word for the bird, only for the fool; the
    # Wiktionary sense that has one must not sit below it.
    with StarDictReader(_directory("en-nl")) as reader:
        body = reader.lookup("geese")[0]
    assert body.index("gans") < body.index("oliebol")


def test_the_spanish_potato_leads_with_the_potato():
    # The sense the corpus tagged has to come first; the lexicon's own order
    # put the vulgar one on top.
    with StarDictReader(_directory("es-pt")) as reader:
        body = reader.lookup("patata")[0]
    assert body.index("batata") < body.index("vagina")
