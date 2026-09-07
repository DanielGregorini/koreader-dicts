"""Downloading and caching source files."""

from __future__ import annotations

import pytest
from kdicts.fetch import FetchError, ensure_source


def _serve(tmp_path, folder, name, text):
    """Write a file and return the file:// URL it can be fetched from."""
    directory = tmp_path / "remote" / folder
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_text(text, encoding="utf-8")
    return path.as_uri()


def test_two_urls_with_the_same_basename_do_not_share_a_cache_entry(tmp_path):
    # Every kaikki edition is published under the same filename, so this is not
    # hypothetical: the cache used to key on the last path segment and hand the
    # second source the first one's bytes.
    spanish = _serve(tmp_path, "eswiktionary", "raw-wiktextract-data.jsonl", "spanish\n")
    french = _serve(tmp_path, "frwiktionary", "raw-wiktextract-data.jsonl", "french\n")
    data = tmp_path / "data"

    first = ensure_source(url=spanish, data_root=data, relative_path="kaikki/es.jsonl")
    second = ensure_source(url=french, data_root=data, relative_path="kaikki/fr.jsonl")

    assert first.read_text(encoding="utf-8") == "spanish\n"
    assert second.read_text(encoding="utf-8") == "french\n"


def test_an_existing_target_is_not_downloaded_again(tmp_path):
    url = _serve(tmp_path, "edition", "data.jsonl", "fresh\n")
    data = tmp_path / "data"
    target = data / "kaikki" / "data.jsonl"
    target.parent.mkdir(parents=True)
    target.write_text("already here\n", encoding="utf-8")

    assert ensure_source(url=url, data_root=data, relative_path="kaikki/data.jsonl") == target
    assert target.read_text(encoding="utf-8") == "already here\n"


def test_a_checksum_mismatch_refuses_the_file(tmp_path):
    url = _serve(tmp_path, "edition", "data.jsonl", "contents\n")
    with pytest.raises(FetchError, match="sha256 mismatch"):
        ensure_source(
            url=url,
            data_root=tmp_path / "data",
            relative_path="kaikki/data.jsonl",
            sha256="0" * 64,
        )
