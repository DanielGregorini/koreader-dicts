"""Measured quality metrics for a generated dictionary.

Everything measured here is written to metrics.json and rendered by the site.

Two rules keep the numbers meaningful:

* Gloss-only senses are never counted as translations. A pivot entry where
  WordNet knows the concept and the target wordnet has no word for it is
  reported on its own line.
* Coverage is measured against a frequency list and counts inflected forms,
  because that is what determines whether a lookup on a real page succeeds.
"""

from __future__ import annotations

import json
import statistics
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from ..ir import Dictionary

__all__ = [
    "COVERAGE_CUTOFFS",
    "Metrics",
    "load_frequency_list",
    "measure",
    "write_metrics",
]

#: Where we probe the frequency list. The top 1k is table stakes; the top 50k is
#: where free dictionaries usually fall apart and where the merge pays off.
COVERAGE_CUTOFFS: tuple[int, ...] = (1_000, 5_000, 10_000, 50_000)


@dataclass(slots=True)
class CoveragePoint:
    cutoff: int
    #: Words in the top *cutoff* that we actually have in the list.
    sampled: int
    #: Found as a headword.
    headword_hits: int
    #: Found only through the .syn inflection index.
    form_hits: int

    @property
    def hits(self) -> int:
        return self.headword_hits + self.form_hits

    @property
    def percent(self) -> float:
        return round(100.0 * self.hits / self.sampled, 2) if self.sampled else 0.0


@dataclass(slots=True)
class Metrics:
    pair: str
    source_lang: str
    target_lang: str
    generated_at: str

    entries: int = 0
    senses: int = 0
    inflected_forms: int = 0

    entries_with_translation: int = 0
    entries_gloss_only: int = 0
    senses_with_translation: int = 0
    senses_gloss_only: int = 0

    entries_with_example: int = 0
    entries_with_pronunciation: int = 0
    entries_with_forms: int = 0

    mean_definition_chars: float = 0.0
    median_definition_chars: float = 0.0
    mean_translations_per_entry: float = 0.0
    mean_forms_per_entry: float = 0.0

    coverage: list[dict[str, object]] = field(default_factory=list)
    frequency_list: str = ""

    licenses: list[str] = field(default_factory=list)
    bundle_license: str = ""
    sources: list[dict[str, str]] = field(default_factory=list)

    #: Published figures for the dictionaries we are competing with, so the
    #: site can show a comparison rather than an unanchored number.

    @property
    def percent_entries_with_translation(self) -> float:
        return round(100.0 * self.entries_with_translation / self.entries, 2) if self.entries else 0.0

    @property
    def percent_entries_with_example(self) -> float:
        return round(100.0 * self.entries_with_example / self.entries, 2) if self.entries else 0.0

    @property
    def percent_entries_with_forms(self) -> float:
        return round(100.0 * self.entries_with_forms / self.entries, 2) if self.entries else 0.0

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["percent_entries_with_translation"] = self.percent_entries_with_translation
        data["percent_entries_with_example"] = self.percent_entries_with_example
        data["percent_entries_with_forms"] = self.percent_entries_with_forms
        return data


def load_frequency_list(path: Path | str, limit: int | None = None) -> list[str]:
    """Read a frequency list: one word per line, most frequent first.

    Lines of the form ``word<whitespace>count`` are accepted too, which is what
    most published lists actually look like.
    """
    words: list[str] = []
    seen: set[str] = set()
    with Path(path).open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            token = line.strip().split()
            if not token:
                continue
            word = token[0].strip().lower()
            if not word or word in seen:
                continue
            seen.add(word)
            words.append(word)
            if limit and len(words) >= limit:
                break
    return words


def _coverage(
    dictionary: Dictionary,
    frequency_words: Sequence[str],
    cutoffs: Iterable[int],
) -> list[CoveragePoint]:
    headwords = {word.lower() for word in dictionary.entries}
    forms = {
        form.lower()
        for entry in dictionary.entries.values()
        for form in entry.forms
    }
    forms -= headwords

    points: list[CoveragePoint] = []
    for cutoff in cutoffs:
        window = frequency_words[:cutoff]
        if not window:
            continue
        headword_hits = sum(1 for word in window if word in headwords)
        form_hits = sum(1 for word in window if word not in headwords and word in forms)
        points.append(
            CoveragePoint(
                cutoff=cutoff,
                sampled=len(window),
                headword_hits=headword_hits,
                form_hits=form_hits,
            )
        )
    return points


def measure(
    dictionary: Dictionary,
    *,
    frequency_words: Sequence[str] = (),
    frequency_list_name: str = "",
    bundle_license: str = "",
    sources: Sequence[dict[str, str]] = (),
    cutoffs: Iterable[int] = COVERAGE_CUTOFFS,
) -> Metrics:
    """Compute every published metric for *dictionary*."""
    metrics = Metrics(
        pair=dictionary.pair,
        source_lang=dictionary.source_lang,
        target_lang=dictionary.target_lang,
        generated_at=datetime.now(UTC).isoformat(timespec="seconds"),
        frequency_list=frequency_list_name,
        bundle_license=bundle_license,
        sources=[dict(s) for s in sources],
        licenses=sorted(dictionary.license_ids),
    )

    definition_lengths: list[int] = []
    translation_counts: list[int] = []
    form_counts: list[int] = []

    for entry in dictionary.entries.values():
        metrics.entries += 1
        metrics.senses += len(entry.senses)

        has_translation = False
        has_example = False
        for sense in entry.senses:
            if sense.translations:
                metrics.senses_with_translation += 1
                has_translation = True
            else:
                metrics.senses_gloss_only += 1
            if sense.examples:
                has_example = True
            if sense.gloss:
                definition_lengths.append(len(sense.gloss))

        if has_translation:
            metrics.entries_with_translation += 1
        else:
            metrics.entries_gloss_only += 1
        if has_example:
            metrics.entries_with_example += 1
        if entry.pronunciations:
            metrics.entries_with_pronunciation += 1
        if entry.forms:
            metrics.entries_with_forms += 1

        translation_counts.append(entry.translation_count)
        form_counts.append(len(entry.forms))

    metrics.inflected_forms = dictionary.form_count
    if definition_lengths:
        metrics.mean_definition_chars = round(statistics.fmean(definition_lengths), 1)
        metrics.median_definition_chars = float(statistics.median(definition_lengths))
    if translation_counts:
        metrics.mean_translations_per_entry = round(statistics.fmean(translation_counts), 2)
    if form_counts:
        metrics.mean_forms_per_entry = round(statistics.fmean(form_counts), 2)

    metrics.coverage = [
        {
            "cutoff": point.cutoff,
            "sampled": point.sampled,
            "headword_hits": point.headword_hits,
            "form_hits": point.form_hits,
            "hits": point.hits,
            "percent": point.percent,
        }
        for point in _coverage(dictionary, frequency_words, cutoffs)
    ]
    return metrics


def write_metrics(metrics: Metrics, path: Path | str) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(metrics.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path
