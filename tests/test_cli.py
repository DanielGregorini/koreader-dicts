"""The command line, which is the interface the build farm actually uses."""

from __future__ import annotations

import json

import pytest
from fixtures import write_omw_lmf, write_wordnet
from kdicts.cli import main


@pytest.fixture()
def project(tmp_path):
    data = tmp_path / "data"
    configs = tmp_path / "configs"
    (configs / "pairs").mkdir(parents=True)
    data.mkdir()
    write_wordnet(data)
    write_omw_lmf(data, "omw-pt", "pt", "https://creativecommons.org/licenses/by-sa/")
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
""",
        encoding="utf-8",
    )
    (configs / "pairs" / "en-pt.toml").write_text(
        """
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

[inflections]
wordnet_exceptions = "pwn30"
rules = true
""",
        encoding="utf-8",
    )
    return tmp_path, data, configs


def run(args, project):
    _tmp_path, data, configs = project
    return main([*args, "--configs", str(configs), "--data", str(data)])


def test_sources_lists_state(project, capsys):
    assert run(["sources"], project) == 0
    out = capsys.readouterr().out
    assert "pwn30" in out and "omw-pt" in out
    assert "present" in out
    assert "unpinned" in out


def test_build_then_verify_then_lookup(project, capsys):
    tmp_path, _data, _configs = project
    out_dir = tmp_path / "build"
    assert run(["build", "en-pt", "--out", str(out_dir)], project) == 0

    directory = out_dir / "en-pt" / "en-pt-test"
    assert main(["verify", str(directory), "--sample", "10000"]) == 0

    assert main(["lookup", str(directory), "dog"]) == 0
    assert "cão" in capsys.readouterr().out

    # A word that is not there must be reported as a failure, not silently
    # succeed -- this is the check that would catch a broken index.
    assert main(["lookup", str(directory), "nonexistentword"]) == 1


def test_catalog_reflects_what_has_been_built(project, capsys):
    tmp_path, _data, _configs = project
    out_dir = tmp_path / "build"

    assert run(["catalog", "--out", str(out_dir)], project) == 0
    catalog = json.loads((out_dir / "catalog.json").read_text())
    assert catalog["dictionaries"][0]["built"] is False

    run(["build", "en-pt", "--out", str(out_dir)], project)
    assert run(["catalog", "--out", str(out_dir)], project) == 0
    catalog = json.loads((out_dir / "catalog.json").read_text())
    record = catalog["dictionaries"][0]
    assert record["built"] is True
    assert record["metrics"]["entries"] > 0
    assert record["name"] == "English to Portuguese"


def test_unknown_pair_is_an_error(project, capsys):
    tmp_path, _data, _configs = project
    assert run(["build", "nope", "--out", str(tmp_path / "build")], project) == 1
    assert "unknown pair" in capsys.readouterr().err


def test_bad_config_exits_cleanly(project, capsys):
    _tmp_path, _data, configs = project
    (configs / "sources.toml").write_text("this is not toml = = =", encoding="utf-8")
    assert run(["sources"], project) == 2
    assert "error:" in capsys.readouterr().err
