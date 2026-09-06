"""End-to-end tests for the StarDict writer.

Every generated dictionary must be verifiable by parsing the output back and
binary-searching it with a comparator transcribed from StarDict's own C, which
is what :mod:`kdicts.verify.stardict_reader` provides.
"""

from __future__ import annotations

import functools
import itertools
import struct

import pytest
from conftest import random_word
from kdicts.verify.stardict_reader import StarDictReader
from kdicts.verify.stardict_reader import stardict_strcmp as reference_strcmp
from kdicts.writers.stardict import IfoMeta, StarDictError, write_stardict


def meta(**kwargs) -> IfoMeta:
    base = {
        "bookname": "Test EN-PT",
        "author": "koreader-dicts",
        "description": "Built from WordNet 3.0 and OpenWN-PT.",
        "date": "2026.09.06",
    }
    base.update(kwargs)
    return IfoMeta(**base)


def build(tmp_path, words, *, synonyms=(), **kwargs):
    entries = [(word, f"<b>{word}</b> definition") for word in words]
    report = write_stardict(tmp_path, "test-dict", entries, meta(), synonyms=synonyms, **kwargs)
    return report


# --- file shape --------------------------------------------------------------


def test_writes_the_expected_files(tmp_path):
    report = build(tmp_path, ["alpha", "beta"], synonyms=[("alphas", "alpha")])
    assert report.ifo_path.name == "test-dict.ifo"
    assert report.dict_path.name == "test-dict.dict.dz"
    assert report.syn_path is not None
    names = sorted(p.name for p in report.directory.iterdir())
    assert names == ["test-dict.dict.dz", "test-dict.idx", "test-dict.ifo", "test-dict.syn"]
    # The uncompressed body must not be left behind next to the .dz.
    assert not (report.directory / "test-dict.dict").exists()


def test_uncompressed_output(tmp_path):
    report = build(tmp_path, ["alpha", "beta"], compress=False)
    assert report.dict_path.name == "test-dict.dict"
    with StarDictReader(report.directory) as reader:
        assert reader.lookup("alpha")


def test_ifo_contents(tmp_path):
    report = build(tmp_path, ["alpha", "beta"], synonyms=[("alphas", "alpha")])
    lines = report.ifo_path.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "StarDict's dict ifo file"
    assert lines[1] == "version=2.4.2"
    fields = dict(line.split("=", 1) for line in lines[1:])
    assert fields["wordcount"] == "2"
    assert fields["synwordcount"] == "1"
    assert fields["idxfilesize"] == str(report.idx_path.stat().st_size)
    assert fields["sametypesequence"] == "h"


def test_ifo_omits_synwordcount_without_a_syn_file(tmp_path):
    report = build(tmp_path, ["alpha"])
    assert report.syn_path is None
    assert "synwordcount" not in report.ifo_path.read_text(encoding="utf-8")


def test_ifo_description_is_flattened_to_one_line(tmp_path):
    """A newline in the description silently truncates our attribution."""
    text = "Sources:\nWordNet 3.0\r\nOpenWN-PT"
    report = write_stardict(
        tmp_path, "d", [("a", "x")], meta(description=text), compress=False
    )
    body = report.ifo_path.read_text(encoding="utf-8")
    assert "description=Sources:<br>WordNet 3.0<br>OpenWN-PT" in body
    with StarDictReader(report.directory) as reader:
        assert "WordNet 3.0" in reader.ifo["description"]


# --- ordering ----------------------------------------------------------------


def test_idx_is_sorted_by_the_c_comparator(tmp_path, nasty_words):
    report = build(tmp_path, nasty_words)
    with StarDictReader(report.directory) as reader:
        words = [entry.word for entry in reader.entries]
    assert words == sorted(words, key=functools.cmp_to_key(reference_strcmp))
    for previous, current in itertools.pairwise(words):
        assert reference_strcmp(previous, current) < 0, (previous, current)


def test_syn_is_sorted_by_the_c_comparator(tmp_path, nasty_words):
    synonyms = [(word + "s", word) for word in nasty_words]
    report = build(tmp_path, nasty_words, synonyms=synonyms)
    with StarDictReader(report.directory) as reader:
        forms = [form for form, _ in reader.synonyms]
    assert forms == sorted(forms, key=functools.cmp_to_key(reference_strcmp))


def test_input_order_does_not_affect_output(tmp_path, nasty_words, rng):
    shuffled = list(nasty_words)
    rng.shuffle(shuffled)
    a = build(tmp_path / "a", nasty_words, compress=False)
    b = build(tmp_path / "b", shuffled, compress=False)
    assert a.idx_path.read_bytes() == b.idx_path.read_bytes()
    assert a.dict_path.read_bytes() == b.dict_path.read_bytes()


# --- offset integrity --------------------------------------------------------


def test_offsets_are_contiguous_and_cover_the_body(tmp_path, nasty_words):
    report = build(tmp_path, nasty_words, compress=False)
    with StarDictReader(report.directory) as reader:
        cursor = 0
        for entry in reader.entries:
            assert entry.offset == cursor, "gap or overlap in the .dict body"
            assert entry.size > 0
            cursor += entry.size
        assert cursor == report.dict_path.stat().st_size
        assert cursor == report.dictfilesize


def test_idx_record_layout(tmp_path):
    """word bytes, NUL, then two big-endian uint32s."""
    report = build(tmp_path, ["ação"], compress=False)
    blob = report.idx_path.read_bytes()
    expected = "ação".encode()
    assert blob[: len(expected)] == expected
    assert blob[len(expected)] == 0
    offset, size = struct.unpack(">II", blob[len(expected) + 1 : len(expected) + 9])
    assert offset == 0
    assert size == report.dictfilesize
    assert len(blob) == len(expected) + 9


def test_syn_record_layout(tmp_path):
    report = build(tmp_path, ["wield"], synonyms=[("wielded", "wield")], compress=False)
    blob = report.syn_path.read_bytes()
    assert blob == b"wielded\x00" + struct.pack(">I", 0)


# --- round trips -------------------------------------------------------------


def test_every_headword_is_findable_by_binary_search(tmp_path, nasty_words):
    report = build(tmp_path, nasty_words)
    with StarDictReader(report.directory) as reader:
        for word in nasty_words:
            normalised = " ".join(word.split())
            hits = reader.find_idx(normalised)
            assert hits, f"binary search lost {word!r}"
            assert reader.definition_at(hits[0]) == f"<b>{normalised}</b> definition"


@pytest.mark.parametrize("count", [2000])
def test_large_random_dictionary_round_trips(tmp_path, rng, count):
    # Compare against the normalised form: the writer collapses internal
    # whitespace, so two raw inputs can legitimately become one headword.
    words = {" ".join(random_word(rng).split()) for _ in range(count)}
    words.discard("")
    report = build(tmp_path, sorted(words))
    assert report.wordcount == len(words)
    with StarDictReader(report.directory) as reader:
        assert len(reader.entries) == len(words)
        for word in words:
            hits = reader.find_idx(word)
            assert hits, f"lost {word!r}"
            assert reader.definition_at(hits[0]) == f"<b>{word}</b> definition"


def test_round_trip_through_dictzip_matches_uncompressed(tmp_path, nasty_words):
    plain = build(tmp_path / "plain", nasty_words, compress=False)
    zipped = build(tmp_path / "zipped", nasty_words, compress=True)
    with StarDictReader(plain.directory) as a, StarDictReader(zipped.directory) as b:
        assert a.headwords() == b.headwords()
        for index in range(len(a.entries)):
            assert a.definition_at(index) == b.definition_at(index)


def test_synonyms_resolve_to_their_headword(tmp_path):
    words = ["wield", "leaf", "go"]
    synonyms = [
        ("wielded", "wield"), ("wielding", "wield"), ("wields", "wield"),
        ("leaves", "leaf"), ("went", "go"), ("gone", "go"),
    ]
    report = build(tmp_path, words, synonyms=synonyms)
    assert report.synwordcount == 6
    with StarDictReader(report.directory) as reader:
        assert reader.lookup("wielded") == ["<b>wield</b> definition"]
        assert reader.lookup("went") == ["<b>go</b> definition"]
        assert reader.lookup("leaves") == ["<b>leaf</b> definition"]


def test_synonyms_accept_a_mapping(tmp_path):
    report = build(tmp_path, ["wield"], synonyms={"wield": ["wielded", "wields"]})
    assert report.synwordcount == 2
    with StarDictReader(report.directory) as reader:
        assert reader.lookup("wields") == ["<b>wield</b> definition"]


def test_ascii_case_insensitive_lookup(tmp_path):
    report = build(tmp_path, ["dog"])
    with StarDictReader(report.directory) as reader:
        # Exact search is case-sensitive at the strcmp tiebreak...
        assert reader.find_idx("Dog") == []
        # ...but the sdcv-style variant retry finds it, as on a real device.
        assert reader.lookup("Dog") == ["<b>dog</b> definition"]


# --- rejections and guards ---------------------------------------------------


def test_overlong_headword_is_rejected(tmp_path):
    long_word = "á" * 200  # 400 UTF-8 bytes
    report = write_stardict(tmp_path, "d", [("ok", "x"), (long_word, "y")], meta())
    assert report.wordcount == 1
    assert any("exceeds" in reason for _, reason in report.skipped)


def test_boundary_length_headword_is_kept(tmp_path):
    exact = "a" * 255
    report = write_stardict(tmp_path, "d", [(exact, "x")], meta())
    assert report.wordcount == 1
    assert report.skipped == []


def test_nul_in_definition_is_rejected(tmp_path):
    report = write_stardict(tmp_path, "d", [("ok", "x"), ("bad", "a\x00b")], meta())
    assert report.wordcount == 1
    assert report.skipped == [("bad", "definition contains a NUL byte")]


def test_empty_and_whitespace_headwords_are_rejected(tmp_path):
    report = write_stardict(tmp_path, "d", [("ok", "x"), ("", "y"), ("   ", "z")], meta())
    assert report.wordcount == 1
    assert len(report.skipped) == 2


def test_headword_whitespace_is_normalised(tmp_path):
    report = write_stardict(tmp_path, "d", [("  St.   John  ", "x")], meta())
    with StarDictReader(report.directory) as reader:
        assert reader.headwords() == ["St. John"]


def test_strict_mode_raises_instead_of_skipping(tmp_path):
    with pytest.raises(StarDictError):
        write_stardict(tmp_path, "d", [("ok", "x"), ("", "y")], meta(), strict=True)


def test_empty_dictionary_is_refused(tmp_path):
    with pytest.raises(StarDictError, match="zero entries"):
        write_stardict(tmp_path, "d", [], meta())


def test_duplicate_headwords_are_merged(tmp_path):
    report = write_stardict(
        tmp_path, "d", [("run", "<b>one</b>"), ("run", "<b>two</b>")], meta(), compress=False
    )
    assert report.wordcount == 1
    assert report.merged_duplicates == 1
    with StarDictReader(report.directory) as reader:
        assert reader.lookup("run") == ["<b>one</b><b>two</b>"]


def test_duplicate_headwords_can_be_rejected(tmp_path):
    report = write_stardict(
        tmp_path, "d", [("run", "a"), ("run", "b")], meta(), merge_duplicates=False
    )
    assert report.wordcount == 1
    assert report.skipped == [("run", "duplicate headword")]


def test_dangling_synonym_is_dropped(tmp_path):
    report = build(tmp_path, ["wield"], synonyms=[("xxx", "not-a-headword")])
    assert report.dangling_synonyms == 1
    assert report.syn_path is None


def test_self_referential_synonym_is_dropped(tmp_path):
    """A form identical to its headword is already found by the idx search."""
    report = build(tmp_path, ["wield"], synonyms=[("wield", "wield"), ("wielded", "wield")])
    assert report.synwordcount == 1


def test_repeated_synonym_pairs_are_deduplicated(tmp_path):
    report = build(tmp_path, ["wield"], synonyms=[("wielded", "wield")] * 3)
    assert report.synwordcount == 1
