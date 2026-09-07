"""End to end: config -> sources -> pivot -> enrich -> StarDict -> verify.

Every generated dictionary must be verifiable by a script that parses the
output back and binary-searches it. This is that script, run against miniature
sources so it can live in the test suite.
"""

from __future__ import annotations

import json

import pytest
from fixtures import write_kaikki, write_omw_lmf, write_wordnet
from kdicts.config import load_all_pairs, load_pair, load_sources
from kdicts.pipeline import BuildError, build_pair, verify_output
from kdicts.verify.stardict_reader import StarDictReader


@pytest.fixture()
def workspace(tmp_path):
    """A data root and config directory holding miniature versions of everything."""
    data = tmp_path / "data"
    configs = tmp_path / "configs"
    (configs / "pairs").mkdir(parents=True)
    data.mkdir()

    write_wordnet(data)
    write_omw_lmf(data, "omw-pt", "pt", "https://creativecommons.org/licenses/by-sa/")
    write_omw_lmf(data, "omw-es", "es", "https://creativecommons.org/licenses/by/3.0/",
                  entries=[("perro", "n", [("02084071", "n")]),
                           ("diablo", "n", [("09542339", "n")]),
                           ("perseguir", "v", [("02001858", "v")])])
    write_omw_lmf(data, "omw-fr", "fr",
                  "http://www.cecill.info/licenses/Licence_CeCILL-C_V1-en.html",
                  entries=[("chien", "n", [("02084071", "n")])])
    write_kaikki(data, edition="pt")
    write_kaikki(data, edition="en")
    (data / "freq").mkdir()
    (data / "freq" / "en.txt").write_text("dog 100\ndevil 50\nchase 20\nnothere 1\n", encoding="utf-8")

    (configs / "sources.toml").write_text(
        """
[[source]]
id = "pwn30"
kind = "wordnet"
path = "dict"
lang = "en"
license_id = "WordNet-3.0"
credit = "Princeton University WordNet 3.0"

[[source]]
id = "omw-pt"
kind = "omw-lmf"
path = "omw-pt.xml"
lang = "pt"
license_id = "CC-BY-SA-4.0"
credit = "OpenWN-PT"

[[source]]
id = "omw-es"
kind = "omw-lmf"
path = "omw-es.xml"
lang = "es"
license_id = "CC-BY-3.0"
credit = "MCR Spanish"

[[source]]
id = "omw-fr"
kind = "omw-lmf"
path = "omw-fr.xml"
lang = "fr"
license_id = "CECILL-C"
credit = "WOLF"

[[source]]
id = "wikt-pt"
kind = "kaikki"
path = "ptwiktionary.jsonl"
lang = "pt"
license_id = "CC-BY-SA-4.0"
credit = "Portuguese Wiktionary"
options = { mode = "foreign_entries", source_lang = "en", target_lang = "pt" }

[[source]]
id = "wikt-en"
kind = "kaikki"
path = "enwiktionary.jsonl"
lang = "en"
license_id = "CC-BY-SA-4.0"
credit = "English Wiktionary"
options = { mode = "translations", source_lang = "en", target_lang = "pt" }
""",
        encoding="utf-8",
    )
    return data, configs


def write_pair(configs, name, body):
    path = configs / "pairs" / f"{name}.toml"
    path.write_text(body, encoding="utf-8")
    return path


EN_PT = """
id = "en-pt"
source_lang = "en"
target_lang = "pt"
name = "English to Portuguese"
bookname = "English-Portuguese (test)"
basename = "en-pt-test"

[pivot]
source_side = "pwn30"
target_side = "omw-pt"
gloss_providers = ["pwn30"]
gloss_langs = ["pt", "en"]

[[enrich]]
source = "wikt-pt"

[[enrich]]
source = "wikt-en"

[inflections]
wordnet_exceptions = "pwn30"
rules = true
from_sources = ["wikt-pt", "wikt-en"]

[benchmark]
frequency_list = "freq/en.txt"
frequency_list_name = "test list"
"""


def build(workspace, tmp_path, body=EN_PT, name="en-pt", **kwargs):
    data, configs = workspace
    write_pair(configs, name, body)
    pair = load_pair(configs / "pairs" / f"{name}.toml")
    sources = load_sources(configs / "sources.toml")
    return build_pair(pair, sources, data_root=data, out_root=tmp_path / "build", **kwargs)


# --- the happy path ----------------------------------------------------------


def test_builds_a_usable_dictionary(workspace, tmp_path):
    result = build(workspace, tmp_path)
    assert result.report.wordcount > 0
    assert result.bundle_license_id == "CC-BY-SA-4.0"
    assert result.report.syn_path is not None

    with StarDictReader(result.directory) as reader:
        assert "cão" in reader.lookup("dog")[0]
        # The Portuguese Wiktionary entry was merged into the same headword.
        assert "canídeos" in reader.lookup("dog")[0]
        # Irregular form, from WordNet's exception files.
        assert reader.lookup("went")
        # Regular form, from the morphological rules.
        assert reader.lookup("dogs")


def test_output_passes_independent_verification(workspace, tmp_path):
    result = build(workspace, tmp_path)
    assert verify_output(result.directory, sample=10_000) == []


def test_attribution_ships_inside_and_beside_the_artifact(workspace, tmp_path):
    result = build(workspace, tmp_path)
    # Inside: the .ifo description survives being separated from the package.
    ifo = result.report.ifo_path.read_text(encoding="utf-8")
    assert "CC-BY-SA-4.0" in ifo
    assert "Princeton University WordNet 3.0" in ifo
    assert "Not affiliated with the KOReader project" in ifo
    assert ifo.count("\n") == len(ifo.strip().splitlines())  # no value spans lines

    # Beside: the files a redistributor has to honour.
    attribution = (result.directory / "ATTRIBUTION").read_text(encoding="utf-8")
    assert "must be retained on all copies" in attribution
    assert "OpenWN-PT" in attribution
    assert (result.directory / "LICENSE").exists()
    readme = (result.directory / "README.txt").read_text(encoding="utf-8")
    assert "koreader/data/dict/" in readme


def test_metrics_are_written_and_honest(workspace, tmp_path):
    result = build(workspace, tmp_path)
    metrics = json.loads((tmp_path / "build" / "en-pt" / "metrics.json").read_text())
    assert metrics["pair"] == "en-pt"
    assert metrics["entries"] == result.report.wordcount
    # Gloss-only senses must never be reported as translations.
    assert metrics["senses_with_translation"] + metrics["senses_gloss_only"] == metrics["senses"]
    assert metrics["entries_with_translation"] + metrics["entries_gloss_only"] == metrics["entries"]
    assert metrics["bundle_license"] == "CC-BY-SA-4.0"
    assert sorted(metrics["licenses"]) == ["CC-BY-SA-4.0", "WordNet-3.0"]
    assert {s["id"] for s in metrics["sources"]} == {"pwn30", "omw-pt", "wikt-pt", "wikt-en"}

    coverage = {c["cutoff"]: c for c in metrics["coverage"]}
    assert coverage[1000]["sampled"] == 4
    assert coverage[1000]["hits"] == 3  # dog, devil, chase; "nothere" is absent


# --- the pivot generalises ---------------------------------------------------


def test_a_new_pair_is_a_config_file_and_nothing_else(workspace, tmp_path):
    """es->pt with no Spanish-Portuguese resource anywhere in the inputs."""
    result = build(
        workspace, tmp_path, name="es-pt", body="""
id = "es-pt"
source_lang = "es"
target_lang = "pt"
name = "Spanish to Portuguese"
bookname = "Spanish-Portuguese (test)"
basename = "es-pt-test"

[pivot]
source_side = "omw-es"
target_side = "omw-pt"
gloss_providers = ["pwn30"]
keep_gloss_only = false
""")
    with StarDictReader(result.directory) as reader:
        assert "cão" in reader.lookup("perro")[0]
        assert "perseguir" in reader.lookup("perseguir")[0]
    # CC BY 3.0 material can be folded into a CC BY-SA 4.0 bundle.
    assert result.bundle_license_id == "CC-BY-SA-4.0"


def test_reverse_direction(workspace, tmp_path):
    result = build(
        workspace, tmp_path, name="pt-en", body="""
id = "pt-en"
source_lang = "pt"
target_lang = "en"
name = "Portuguese to English"
bookname = "Portuguese-English (test)"
basename = "pt-en-test"

[pivot]
source_side = "omw-pt"
target_side = "pwn30"
gloss_providers = ["pwn30"]
keep_gloss_only = false
""")
    with StarDictReader(result.directory) as reader:
        body = reader.lookup("cão")[0]
        assert "dog" in body and "domestic dog" in body


# --- the licence guard -------------------------------------------------------


FR_CONFLICT = """
id = "en-fr"
source_lang = "en"
target_lang = "fr"
name = "English to French"
bookname = "English-French (test)"
basename = "en-fr-test"

[pivot]
source_side = "pwn30"
target_side = "omw-fr"
gloss_providers = ["pwn30"]

[[enrich]]
source = "wikt-pt"
"""


def test_incompatible_licences_fail_loudly(workspace, tmp_path):
    """CeCILL-C (WOLF) plus CC BY-SA (Wiktionary) has no lawful outbound licence.

    The build must stop rather than emit a file whose terms cannot be stated.
    """
    with pytest.raises(BuildError, match="separate bundles"):
        build(workspace, tmp_path, name="en-fr", body=FR_CONFLICT)


def test_dropping_incompatible_material_is_opt_in_and_reported(workspace, tmp_path):
    result = build(workspace, tmp_path, name="en-fr", body=FR_CONFLICT, drop_incompatible=True)
    assert result.dropped_sources
    assert result.bundle_license_id != "UNKNOWN"
    assert any("dropped material" in note for note in result.notes)


def test_cecill_c_alone_ships_as_its_own_bundle(workspace, tmp_path):
    """WOLF is fine on its own; it just cannot be mixed with CC BY-SA."""
    result = build(workspace, tmp_path, name="en-fr", body="""
id = "en-fr"
source_lang = "en"
target_lang = "fr"
name = "English to French"
bookname = "English-French (test)"
basename = "en-fr-test"

[pivot]
source_side = "pwn30"
target_side = "omw-fr"
gloss_providers = ["pwn30"]
keep_gloss_only = false
""")
    assert result.bundle_license_id == "CECILL-C"


# --- failure modes -----------------------------------------------------------


def test_missing_source_data_says_what_to_run(workspace, tmp_path):
    data, _configs = workspace
    (data / "omw-pt.xml").unlink()
    with pytest.raises(Exception, match="kdicts fetch"):
        build(workspace, tmp_path)


def test_pair_referencing_an_undeclared_source_is_rejected(workspace, tmp_path):
    with pytest.raises(BuildError, match=r"not.*declared"):
        build(workspace, tmp_path, name="broken", body="""
id = "broken"
source_lang = "en"
target_lang = "pt"
name = "Broken"
bookname = "Broken"
basename = "broken"

[pivot]
source_side = "pwn30"
target_side = "omw-nonexistent"
""")


def test_shipped_pair_configs_all_load():
    """The configs in the repository must stay loadable, not just the fixtures."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    sources = load_sources(root / "configs" / "sources.toml")
    pairs = load_all_pairs(root / "configs" / "pairs")
    assert pairs
    for pair in pairs.values():
        for source_id in pair.source_ids():
            assert source_id in sources, f"{pair.id} references undeclared source {source_id}"


# --- packaging ---------------------------------------------------------------


def test_build_produces_a_downloadable_archive(workspace, tmp_path):
    import zipfile

    result = build(workspace, tmp_path)
    assert result.archive is not None
    assert result.archive.exists()
    assert result.archive.name == "en-pt-test.zip"

    with zipfile.ZipFile(result.archive) as archive:
        names = archive.namelist()
        assert archive.testzip() is None
        # Every member sits under the dictionary folder, so unzipping into
        # koreader/data/dict/ lands the files at exactly the right depth.
        assert all(name.startswith("en-pt-test/") for name in names), names
        assert "en-pt-test/en-pt-test.ifo" in names
        assert "en-pt-test/en-pt-test.idx" in names
        assert "en-pt-test/ATTRIBUTION" in names
        # DEFLATE, not stored: readers download this over mobile connections.
        assert all(
            info.compress_type == zipfile.ZIP_DEFLATED
            for info in archive.infolist()
            if info.file_size > 0
        )


def test_archive_can_be_skipped(workspace, tmp_path):
    result = build(workspace, tmp_path, make_archive=False)
    assert result.archive is None
    assert not (result.directory.parent / "en-pt-test.zip").exists()
