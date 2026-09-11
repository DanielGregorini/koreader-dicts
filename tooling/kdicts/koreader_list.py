"""The entries KOReader's built-in dictionary downloader needs.

KOReader lists downloadable dictionaries in ``frontend/ui/data/dictionaries.lua``
as Lua tables with a name, ISO 639-3 language codes, an entry count, a licence
and a URL. This writes that list for every built dictionary that clears a
coverage floor, so the file shipped to KOReader is generated from the catalog
rather than typed.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from .config import PairConfig

__all__ = ["render_koreader_list"]

ISO_639_3 = {
    "en": "eng", "pt": "por", "es": "spa", "it": "ita", "de": "deu", "fr": "fra",
    "ru": "rus", "pl": "pol", "cs": "ces", "nl": "nld", "el": "ell", "fi": "fin",
    "ja": "jpn", "ko": "kor", "zh": "zho", "ar": "ara", "id": "ind",
}
LANGUAGE_NAMES = {
    "en": "English", "pt": "Portuguese", "es": "Spanish", "it": "Italian",
    "de": "German", "fr": "French", "ru": "Russian", "pl": "Polish", "cs": "Czech",
    "nl": "Dutch", "el": "Greek", "fi": "Finnish", "ja": "Japanese", "ko": "Korean",
    "zh": "Chinese", "ar": "Arabic", "id": "Indonesian",
}
# KOReader shows the licence as free text; these are the spellings its list uses.
LICENCE_LABELS = {
    "CC-BY-SA-4.0": "CC BY-SA 4.0", "CC-BY-SA-3.0": "CC BY-SA 3.0",
    "CC-BY-4.0": "CC BY 4.0", "CC-BY-3.0": "CC BY 3.0", "CECILL-C": "CeCILL-C",
    "WordNet-3.0": "WordNet 3.0 License", "MIT": "MIT", "Apache-2.0": "Apache 2.0",
}

_HEADER = """-- koreader-dicts bilingual and monolingual dictionaries for KOReader.
-- Generated from the project's catalog with `kdicts koreader`. Do not edit by hand.
-- Source: https://github.com/DanielGregorini/koreader-dicts
-- Built from Princeton WordNet, the Open Multilingual Wordnet and Wiktionary;
-- every archive carries LICENSE and ATTRIBUTION for the sources it uses.
return {
"""


def _source_label(pair: PairConfig) -> str:
    if pair.pivot and pair.enrich:
        return "WordNet + Wiktionary"
    return "WordNet" if pair.pivot else "Wiktionary"


def _coverage(record: dict[str, Any]) -> float | None:
    for point in record["metrics"].get("coverage", ()):
        if point["cutoff"] == 10000:
            return float(point["percent"])
    return None


def render_koreader_list(
    catalog_path: Path,
    pairs: dict[str, PairConfig],
    *,
    releases_base: str,
    min_coverage: float = 60.0,
    exclude: Iterable[str] = (),
) -> tuple[str, list[str]]:
    """Return the Lua source and the pair ids it lists.

    A pair is left out when its measured coverage is below *min_coverage*.
    Pairs with no frequency list, and so no measurement, are kept.
    """
    catalog = json.loads(Path(catalog_path).read_text(encoding="utf-8"))
    excluded = set(exclude)
    order = list(ISO_639_3)
    rows = []
    for record in catalog["dictionaries"]:
        if not record.get("built") or not record.get("metrics") or record["pair"] in excluded:
            continue
        coverage = _coverage(record)
        if coverage is not None and coverage < min_coverage:
            continue
        rows.append(record)
    rows.sort(
        key=lambda r: (
            order.index(r["source_lang"]),
            r["source_lang"] != r["target_lang"],
            order.index(r["target_lang"]),
        )
    )
    blocks = []
    for record in rows:
        source, target = record["source_lang"], record["target_lang"]
        label = _source_label(pairs[record["pair"]])
        name = (
            f"{LANGUAGE_NAMES[source]} ({label})"
            if source == target
            else f"{LANGUAGE_NAMES[source]}-{LANGUAGE_NAMES[target]} ({label})"
        )
        licence = record["metrics"]["bundle_license"]
        blocks.append(
            "    {\n"
            f'        name = "{name}",\n'
            f'        lang_in = "{ISO_639_3[source]}",\n'
            f'        lang_out = "{ISO_639_3[target]}",\n'
            f"        entries = {record['metrics']['entries']},\n"
            f'        license = "{LICENCE_LABELS.get(licence, licence)}",\n'
            f'        url = "{releases_base}/{record["basename"]}.zip",\n'
            "    },"
        )
    return _HEADER + "\n".join(blocks) + "\n}\n", [r["pair"] for r in rows]
