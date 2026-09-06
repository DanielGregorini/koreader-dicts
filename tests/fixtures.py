from __future__ import annotations

import gzip
import json
from pathlib import Path

__all__ = ["write_kaikki", "write_omw_lmf", "write_wordnet"]

# Real WordNet data files open with a 29-line copyright header whose lines all
# begin with two spaces; the parsers must skip it.
_WN_HEADER = "  1 This software and database is being provided to you, the LICENSEE,\n" * 2

# synset_offset lex_filenum ss_type w_cnt word lex_id ... p_cnt [ptr...] | gloss
_DATA_NOUN = [
    '02084071 05 n 02 dog 0 domestic_dog 0 001 @ 02083346 n 0000 | a member of the genus Canis; "the dog barked all night"  ',
    '10023039 18 n 01 dog 0 000 | a dull unattractive unpleasant girl  ',
    '09542339 09 n 01 devil 0 000 | (Judeo-Christian and Islamic religions) chief spirit of evil  ',
    '01858441 05 n 01 goose 0 000 | web-footed long-necked bird  ',
]
_DATA_VERB = [
    '02001858 35 v 02 chase 0 dog 0 000 01 + 08 00 | go after with intent to catch; "the dog chased the rabbit"  ',
]
_DATA_ADJ = [
    '00003553 00 a 01 whole 0 000 | including all components without exception  ',
    # ss_type "s": an adjective satellite. OMW 1.4 writes these as "-a".
    '00003917 00 s 01 lonely 0 000 | marked by dejection from being alone  ',
]
_DATA_ADV = [
    '00003960 02 r 01 quickly 0 000 | with rapid movements  ',
]

# lemma pos synset_cnt p_cnt [ptr_symbol...] sense_cnt tagsense_cnt offsets...
_INDEX_NOUN = [
    "dog n 2 1 @ 2 1 02084071 10023039  ",
    "domestic_dog n 1 1 @ 1 0 02084071  ",
    "devil n 1 0 1 0 09542339  ",
    "goose n 1 0 1 0 01858441  ",
]
_INDEX_VERB = ["chase v 1 1 @ 1 1 02001858  ", "dog v 1 1 @ 1 0 02001858  "]
_INDEX_ADJ = ["whole a 1 0 1 1 00003553  ", "lonely a 1 0 1 0 00003917  "]
_INDEX_ADV = ["quickly r 1 0 1 1 00003960  "]

_EXCEPTIONS = {
    "noun.exc": "geese goose\naxes ax axis\n",
    "verb.exc": "went go\nwields wield\n",
    "adj.exc": "better good\n",
    "adv.exc": "best well\n",
}


def write_wordnet(tmp_path: Path, name: str = "dict") -> Path:
    """A miniature WNdb ``dict/`` directory."""
    root = Path(tmp_path) / name
    root.mkdir(parents=True, exist_ok=True)
    for filename, lines in (
        ("data.noun", _DATA_NOUN), ("data.verb", _DATA_VERB),
        ("data.adj", _DATA_ADJ), ("data.adv", _DATA_ADV),
        ("index.noun", _INDEX_NOUN), ("index.verb", _INDEX_VERB),
        ("index.adj", _INDEX_ADJ), ("index.adv", _INDEX_ADV),
    ):
        (root / filename).write_text(_WN_HEADER + "\n".join(lines) + "\n", encoding="utf-8")
    for filename, body in _EXCEPTIONS.items():
        (root / filename).write_text(body, encoding="utf-8")
    return root


_LMF_ENTRIES = [
    ("cão", "n", [("02084071", "n")]),
    ("cachorro", "n", [("02084071", "n")]),
    ("diabo", "n", [("09542339", "n")]),
    ("ganso", "n", [("01858441", "n")]),
    ("perseguir", "v", [("02001858", "v")]),
    ("inteiro", "a", [("00003553", "a")]),
    ("solitário", "a", [("00003917", "a")]),
]


def write_omw_lmf(
    tmp_path: Path,
    lexicon_id: str = "omw-pt",
    language: str = "pt",
    license_url: str = "https://creativecommons.org/licenses/by-sa/",
    *,
    definitions: bool = False,
    entries: list[tuple[str, str, list[tuple[str, str]]]] | None = None,
) -> Path:
    """A miniature WN-LMF 1.1 lexicon, as OMW 1.4 actually ships them."""
    entries = entries if entries is not None else _LMF_ENTRIES
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<LexicalResource xmlns:dc="https://globalwordnet.github.io/schemas/dc/">',
        f'  <Lexicon id="{lexicon_id}" label="Test Wordnet" language="{language}"',
        f'           license="{license_url}" version="1.4">',
    ]
    synsets: dict[str, str] = {}
    for lemma, pos, senses in entries:
        lines.append(f'    <LexicalEntry id="{lexicon_id}-{lemma}-{pos}">')
        lines.append(f'      <Lemma writtenForm="{lemma}" partOfSpeech="{pos}" />')
        for offset, tag in senses:
            lines.append(
                f'      <Sense id="{lexicon_id}-{lemma}-{offset}-{tag}" '
                f'synset="{lexicon_id}-{offset}-{tag}" />'
            )
            synsets[f"{offset}-{tag}"] = tag
        lines.append("    </LexicalEntry>")
    for synset, tag in synsets.items():
        if definitions and synset == "02084071-n":
            lines.append(f'    <Synset id="{lexicon_id}-{synset}" partOfSpeech="{tag}">')
            lines.append("      <Definition>mamífero da família dos canídeos</Definition>")
            lines.append("      <Example>o cão latiu a noite toda</Example>")
            lines.append("    </Synset>")
        else:
            lines.append(f'    <Synset id="{lexicon_id}-{synset}" partOfSpeech="{tag}" />')
    lines += ["  </Lexicon>", "</LexicalResource>", ""]

    path = Path(tmp_path) / f"{lexicon_id}.xml"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


_KAIKKI_EN = [
    {
        "word": "dog", "pos": "noun", "lang_code": "en", "lang": "English",
        "senses": [{"glosses": ["A domesticated carnivorous mammal."]}],
        "forms": [
            {"form": "dogs", "tags": ["plural"]},
            {"form": "inu", "tags": ["romanization"]},
            {"form": "-", "tags": ["plural"]},
        ],
        "translations": [
            {"lang": "Portuguese", "code": "pt", "word": "cão"},
            {"lang": "Portuguese", "code": "pt", "word": "cachorro"},
            {"lang": "Spanish", "code": "es", "word": "perro"},
        ],
        "sounds": [{"ipa": "/dɔɡ/"}],
    },
    {
        # Sense-level translations, which is where the English edition puts the
        # overwhelming majority of them.
        "word": "bank", "pos": "noun", "lang_code": "en", "lang": "English",
        "senses": [
            {"glosses": ["An edge of a river."],
             "translations": [{"lang": "Portuguese", "code": "pt", "word": "margem"}]},
            {"glosses": ["A financial institution."],
             "translations": [{"lang": "Portuguese", "code": "pt", "word": "banco"},
                              {"lang": "Spanish", "code": "es", "word": "banco"}]},
        ],
    },
    {
        "word": "go", "pos": "verb", "lang_code": "en", "lang": "English",
        "senses": [{"glosses": ["To move from one place to another."]}],
        "forms": [{"form": "goes", "tags": ["present", "third-person", "singular"]}],
        "translations": [{"lang": "Portuguese", "code": "pt", "word": "ir"}],
    },
    {
        "word": "went", "pos": "verb", "lang_code": "en", "lang": "English",
        "senses": [{"glosses": ["simple past of go"], "form_of": [{"word": "go"}]}],
    },
    {
        "word": "cão", "pos": "noun", "lang_code": "pt", "lang": "Portuguese",
        "senses": [{"glosses": ["mamífero"]}],
    },
]

_KAIKKI_PT = [
    {
        "word": "dog", "pos": "noun", "lang_code": "en", "lang": "Inglês",
        "senses": [
            {"glosses": ["cão"]},
            {"glosses": ["animal mamífero da família dos canídeos, domesticado pelo homem"],
             "examples": [{"text": "the dog barked"}], "tags": ["informal"]},
        ],
        "forms": [{"form": "dogs", "tags": ["plural"]}],
        "sounds": [{"ipa": "/dɔɡ/"}],
    },
    {
        "word": "cadeira", "pos": "noun", "lang_code": "pt", "lang": "Português",
        "senses": [{"glosses": ["assento com encosto"]}],
    },
]


def write_kaikki(tmp_path: Path, edition: str = "en", *, compress: bool = False) -> Path:
    """A miniature kaikki.org wiktextract JSONL dump."""
    pages = _KAIKKI_EN if edition == "en" else _KAIKKI_PT
    body = "".join(json.dumps(page, ensure_ascii=False) + "\n" for page in pages)
    path = Path(tmp_path) / f"{edition}wiktionary.jsonl"
    if compress:
        path = path.with_suffix(".jsonl.gz")
        path.write_bytes(gzip.compress(body.encode("utf-8")))
    else:
        path.write_text(body, encoding="utf-8")
    return path