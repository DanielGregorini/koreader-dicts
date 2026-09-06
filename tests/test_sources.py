"""Source adapters, against miniature fixtures in the real on-disk formats."""

from __future__ import annotations

import textwrap

import pytest
from fixtures import write_kaikki, write_omw_lmf, write_wordnet
from kdicts.ir import Pos, canonical_synset
from kdicts.sources import SourceError, SourceSpec, build_source
from kdicts.sources.omw import detect_license
from kdicts.sources.wordnet import parse_gloss

# --- WordNet -----------------------------------------------------------------


def test_parse_gloss_separates_definition_from_examples():
    definition, examples = parse_gloss(
        'a member of the genus Canis; "the dog barked all night"; "a good dog"'
    )
    assert definition == "a member of the genus Canis"
    assert examples == ("the dog barked all night", "a good dog")


def test_parse_gloss_handles_multi_clause_definitions():
    definition, examples = parse_gloss("go after with intent to catch; pursue")
    assert definition == "go after with intent to catch; pursue"
    assert examples == ()


def test_wordnet_lemmas_and_synsets(tmp_path):
    write_wordnet(tmp_path)
    source = build_source(SourceSpec(id="pwn30", kind="wordnet", path="dict", lang="en"), tmp_path)
    lemmas = {(r.lemma, r.synset, r.rank) for r in source.lemmas()}
    assert ("dog", "02084071-n", 1) in lemmas
    assert ("domestic dog", "02084071-n", 1) in lemmas
    assert ("dog", "10023039-n", 2) in lemmas

    synsets = {r.synset: r for r in source.synsets()}
    assert synsets["02084071-n"].gloss == "a member of the genus Canis"
    assert synsets["02084071-n"].examples == ("the dog barked all night",)
    assert synsets["02084071-n"].pos is Pos.NOUN


def test_wordnet_satellite_adjectives_fold_onto_the_a_tag(tmp_path):
    """OMW 1.4 writes satellites as -a, so the canonical id must too."""
    write_wordnet(tmp_path)
    source = build_source(SourceSpec(id="pwn30", kind="wordnet", path="dict", lang="en"), tmp_path)
    ids = {r.synset for r in source.lemmas()}
    assert "00003553-a" in ids, "satellite adjective lost"
    assert not any(i.endswith("-s") for i in ids)
    assert canonical_synset("00003553", "s") == "00003553-a"


def test_wordnet_synset_members_is_the_reverse_mapping(tmp_path):
    write_wordnet(tmp_path)
    source = build_source(SourceSpec(id="pwn30", kind="wordnet", path="dict", lang="en"), tmp_path)
    members = {(s, w) for s, w in source.synset_members()}
    assert ("02084071-n", "dog") in members
    assert ("02084071-n", "domestic dog") in members


def test_wordnet_rejects_a_directory_that_is_not_a_dict(tmp_path):
    (tmp_path / "empty").mkdir()
    with pytest.raises(SourceError, match="WNdb"):
        build_source(SourceSpec(id="x", kind="wordnet", path="empty", lang="en"), tmp_path)


# --- OMW WN-LMF --------------------------------------------------------------


def test_omw_lmf_reads_lemmas_and_strips_the_lexicon_prefix(tmp_path):
    path = write_omw_lmf(tmp_path, "omw-pt", "pt", "https://creativecommons.org/licenses/by-sa/")
    source = build_source(
        SourceSpec(id="omw-pt", kind="omw-lmf", path=path.name, lang="pt"), tmp_path
    )
    assert source.license_id == "CC-BY-SA-4.0"
    assert source.label == "Test Wordnet"
    pairs = {(r.lemma, r.synset) for r in source.lemmas()}
    assert ("cão", "02084071-n") in pairs
    assert ("perseguir", "02001858-v") in pairs


def test_omw_lmf_reads_definitions_when_present(tmp_path):
    path = write_omw_lmf(
        tmp_path, "omw-pt", "pt", "https://creativecommons.org/licenses/by-sa/", definitions=True
    )
    source = build_source(
        SourceSpec(id="omw-pt", kind="omw-lmf", path=path.name, lang="pt"), tmp_path
    )
    records = {r.synset: r for r in source.synsets()}
    assert records["02084071-n"].gloss == "mamífero da família dos canídeos"


def test_omw_lmf_licence_mismatch_is_a_hard_error(tmp_path):
    """Upstream changing its terms must stop the build, not be absorbed."""
    path = write_omw_lmf(tmp_path, "omw-fr", "fr", "http://www.cecill.info/licenses/Licence_CeCILL-C_V1-en.html")
    with pytest.raises(SourceError, match="config declares licence"):
        build_source(
            SourceSpec(id="omw-fr", kind="omw-lmf", path=path.name, lang="fr",
                       license_id="CC-BY-SA-4.0"),
            tmp_path,
        )


def test_omw_lmf_unparseable_licence_refuses_to_guess(tmp_path):
    path = write_omw_lmf(tmp_path, "omw-xx", "xx", "ask us nicely")
    with pytest.raises(SourceError, match=r"could not interpret the licence"):
        build_source(SourceSpec(id="omw-xx", kind="omw-lmf", path=path.name, lang="xx"), tmp_path)


@pytest.mark.parametrize(
    "declared,expected",
    [
        # Every distinct licence string that appears across OMW 1.4.
        ("https://creativecommons.org/licenses/by-sa/", "CC-BY-SA-4.0"),
        ("https://creativecommons.org/licenses/by-sa/3.0/", "CC-BY-SA-3.0"),
        ("https://creativecommons.org/licenses/by-sa/4.0/", "CC-BY-SA-4.0"),
        ("https://creativecommons.org/licenses/by/3.0/", "CC-BY-3.0"),
        ("wordnet", "WordNet-3.0"),
        ("https://wordnet.princeton.edu/license-and-commercial-use", "WordNet-3.0"),
        ("http://www.cecill.info/licenses/Licence_CeCILL-C_V1-en.html", "CECILL-C"),
        ("https://opensource.org/licenses/MIT/", "MIT"),
        ("https://opensource.org/licenses/Apache-2.0", "Apache-2.0"),
        ("http://opendefinition.org/licenses/odc-by/", "ODC-By-1.0"),
        ("please do not use commercially, CC BY-NC-SA", "CC-BY-NC-SA-4.0"),
        ("", "UNKNOWN"),
    ],
)
def test_licence_detection_covers_every_string_omw_actually_uses(declared, expected):
    assert detect_license(declared) == expected


# --- OMW .tab (older distributions) -----------------------------------------


def test_omw_tab_parses_header_licence_and_canonicalises_ids(tmp_path):
    path = tmp_path / "wn-data-por.tab"
    path.write_text(
        textwrap.dedent(
            """\
            # Portuguese	http://openwordnet-pt.org	CC BY-SA
            02084071-n	por:lemma	cão
            00003553-s	por:lemma	solitário
            02084071-n	por:def	mamífero
            """
        ),
        encoding="utf-8",
    )
    source = build_source(
        SourceSpec(id="omw-pt-tab", kind="omw-tab", path=path.name, lang="pt"), tmp_path
    )
    assert source.license_id == "CC-BY-SA-4.0"
    ids = {r.synset for r in source.lemmas()}
    # The old .tab files spell satellites "-s"; they must land on "-a" so a
    # build can mix a .tab source with an OMW 1.4 one.
    assert ids == {"02084071-n", "00003553-a"}


def test_omw_tab_rejects_ids_that_are_not_pwn30(tmp_path):
    path = tmp_path / "wn-data-xx.tab"
    path.write_text("# x CC BY-SA 4.0\nsomething-else\txx:lemma\tword\n", encoding="utf-8")
    source = build_source(
        SourceSpec(id="bad", kind="omw-tab", path=path.name, lang="xx"), tmp_path
    )
    with pytest.raises(SourceError, match=r"not a PWN 3\.0 synset id"):
        list(source.lemmas())


# --- kaikki ------------------------------------------------------------------


def test_kaikki_translations_mode(tmp_path):
    path = write_kaikki(tmp_path)
    source = build_source(
        SourceSpec(id="wikt-en", kind="kaikki", path=path.name, lang="en",
                   options={"mode": "translations", "source_lang": "en", "target_lang": "pt"}),
        tmp_path,
    )
    entries = {e.headword: e for e in source.entries()}
    assert entries["dog"].senses[0].translations == ("cão", "cachorro")
    assert entries["dog"].pronunciations == ("/dɔɡ/",)
    # The Spanish translation row must not leak into a pt dictionary.
    assert "perro" not in entries["dog"].senses[0].translations


def test_kaikki_reads_sense_level_translations(tmp_path):
    """The English edition puts most translations on senses, not on the page.

    Reading only the page-level table -- the shape most examples show -- drops
    the great majority of the data, and does so silently.
    """
    path = write_kaikki(tmp_path)
    source = build_source(
        SourceSpec(id="wikt-en", kind="kaikki", path=path.name, lang="en",
                   options={"mode": "translations", "source_lang": "en", "target_lang": "pt"}),
        tmp_path,
    )
    bank = {e.headword: e for e in source.entries()}["bank"]
    # Kept per sense, so the riverbank and the financial senses stay apart.
    assert [s.translations for s in bank.senses] == [("margem",), ("banco",)]
    assert bank.senses[0].gloss == "An edge of a river."


def test_kaikki_falls_back_to_page_level_translations(tmp_path):
    path = write_kaikki(tmp_path)
    source = build_source(
        SourceSpec(id="wikt-en", kind="kaikki", path=path.name, lang="en",
                   options={"mode": "translations", "source_lang": "en", "target_lang": "pt"}),
        tmp_path,
    )
    go = {e.headword: e for e in source.entries()}["go"]
    assert go.senses[0].translations == ("ir",)


def test_kaikki_foreign_entries_mode(tmp_path):
    path = write_kaikki(tmp_path, edition="pt")
    source = build_source(
        SourceSpec(id="wikt-pt", kind="kaikki", path=path.name, lang="pt",
                   options={"mode": "foreign_entries", "source_lang": "en", "target_lang": "pt"}),
        tmp_path,
    )
    entries = {e.headword: e for e in source.entries()}
    senses = entries["dog"].senses
    # A short gloss in the reader's language is a translation...
    assert senses[0].translations == ("cão",)
    # ...a long one is a definition and must not be counted as a translation.
    assert senses[1].translations == ()
    assert senses[1].gloss.startswith("animal mamífero")


def test_kaikki_inflections_from_both_signals(tmp_path):
    path = write_kaikki(tmp_path)
    source = build_source(
        SourceSpec(id="wikt-en", kind="kaikki", path=path.name, lang="en",
                   options={"mode": "translations", "source_lang": "en", "target_lang": "pt"}),
        tmp_path,
    )
    pairs = set(source.inflections())
    assert ("dogs", "dog") in pairs          # from the lemma page's form table
    assert ("went", "go") in pairs           # from the inflected page's form_of


def test_kaikki_drops_romanisations_from_forms(tmp_path):
    """A romanisation pointing at a headword would hijack unrelated lookups."""
    path = write_kaikki(tmp_path)
    source = build_source(
        SourceSpec(id="wikt-en", kind="kaikki", path=path.name, lang="en",
                   options={"mode": "translations", "source_lang": "en", "target_lang": "pt"}),
        tmp_path,
    )
    forms = {form for form, _ in source.inflections()}
    assert "inu" not in forms


def test_kaikki_reads_gzip(tmp_path):
    path = write_kaikki(tmp_path, compress=True)
    assert path.suffix == ".gz"
    source = build_source(
        SourceSpec(id="wikt-en", kind="kaikki", path=path.name, lang="en",
                   options={"mode": "translations", "source_lang": "en", "target_lang": "pt"}),
        tmp_path,
    )
    assert any(e.headword == "dog" for e in source.entries())


def test_kaikki_reports_the_line_number_of_bad_json(tmp_path):
    path = tmp_path / "broken.jsonl"
    path.write_text('{"word": "ok", "lang_code": "en"}\nnot json\n', encoding="utf-8")
    source = build_source(
        SourceSpec(id="w", kind="kaikki", path=path.name, lang="en",
                   options={"mode": "translations", "source_lang": "en", "target_lang": "pt"}),
        tmp_path,
    )
    with pytest.raises(SourceError, match=r"broken\.jsonl:2"):
        list(source.entries())


def test_unknown_source_kind_lists_the_known_ones(tmp_path):
    with pytest.raises(SourceError, match="Known kinds"):
        build_source(SourceSpec(id="x", kind="carrier-pigeon", path="."), tmp_path)
