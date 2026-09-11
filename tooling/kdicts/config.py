"""Config loading. A language pair is defined in TOML, never in Python.

Two files:

``configs/sources.toml``
    One entry per *data source instance*: where to fetch it, where it lands on
    disk, what adapter reads it, and what licence it carries.

``configs/pairs/<pair>.toml``
    One entry per *generated dictionary*: which source to pivot from, which to
    pivot to, what to enrich with, and what to benchmark against.

The split is what makes a pair like es-pt cheap: ``es-pt.toml`` names two OMW
wordnets already declared in ``sources.toml`` and adds no new code.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .sources import SourceSpec

__all__ = [
    "BenchmarkSpec",
    "ConfigError",
    "EnrichSpec",
    "InflectionSpec",
    "PairConfig",
    "PivotSpec",
    "load_all_pairs",
    "load_pair",
    "load_sources",
]


class ConfigError(Exception):
    pass


@dataclass(slots=True)
class PivotSpec:
    source_side: str
    target_side: str
    gloss_providers: list[str] = field(default_factory=list)
    gloss_langs: list[str] = field(default_factory=list)
    keep_gloss_only: bool = True
    max_translations: int = 8
    max_senses_per_entry: int = 0


@dataclass(slots=True)
class EnrichSpec:
    source: str
    add_new_headwords: bool = True


@dataclass(slots=True)
class InflectionSpec:
    #: Source id of a WordNet whose ``*.exc`` files supply irregular forms.
    wordnet_exceptions: str = ""
    #: Apply the rule-based inflector to source-language headwords.
    rules: bool = False
    #: Source ids offering an ``inflections()`` stream (kaikki dumps).
    from_sources: list[str] = field(default_factory=list)
    #: Let a form whose lemma is itself a form of one headword attach to that
    #: headword. Needed where an edition keeps lemma pages under another
    #: spelling (Japanese: kana pages, kanji pointers); unsafe as a default,
    #: because elsewhere aliases chain through homographs.
    follow_aliases: bool = False


@dataclass(slots=True)
class BenchmarkSpec:
    frequency_list: str = ""
    frequency_list_name: str = ""


@dataclass(slots=True)
class PairConfig:
    id: str
    source_lang: str
    target_lang: str
    name: str
    bookname: str
    tier: int = 1
    pivot: PivotSpec | None = None
    enrich: list[EnrichSpec] = field(default_factory=list)
    inflections: InflectionSpec = field(default_factory=InflectionSpec)
    benchmark: BenchmarkSpec = field(default_factory=BenchmarkSpec)
    description: str = ""
    basename: str = ""

    def source_ids(self) -> list[str]:
        ids: list[str] = []
        if self.pivot:
            ids += [self.pivot.source_side, self.pivot.target_side, *self.pivot.gloss_providers]
        ids += [e.source for e in self.enrich]
        ids += self.inflections.from_sources
        if self.inflections.wordnet_exceptions:
            ids.append(self.inflections.wordnet_exceptions)
        seen: dict[str, None] = {}
        for source_id in ids:
            seen.setdefault(source_id, None)
        return list(seen)


def _read_toml(path: Path) -> dict[str, Any]:
    try:
        with Path(path).open("rb") as handle:
            return tomllib.load(handle)
    except FileNotFoundError:
        raise ConfigError(f"{path} does not exist") from None
    except tomllib.TOMLDecodeError as error:
        raise ConfigError(f"{path}: {error}") from error


def load_sources(path: Path | str) -> dict[str, SourceSpec]:
    """Read configs/sources.toml into one SourceSpec per declared source."""
    data = _read_toml(Path(path))
    specs: dict[str, SourceSpec] = {}
    for raw in data.get("source", ()):
        try:
            spec = SourceSpec(
                id=raw["id"],
                kind=raw["kind"],
                path=raw["path"],
                lang=raw.get("lang", ""),
                url=raw.get("url", ""),
                version=raw.get("version", ""),
                credit=raw.get("credit", ""),
                license_id=raw.get("license_id", ""),
                sha256=raw.get("sha256", ""),
                archive_member=raw.get("archive_member", ""),
                options=dict(raw.get("options", {})),
            )
        except KeyError as error:
            raise ConfigError(f"{path}: source entry missing {error}") from None
        if spec.id in specs:
            raise ConfigError(f"{path}: duplicate source id {spec.id!r}")
        specs[spec.id] = spec
    if not specs:
        raise ConfigError(f"{path}: no [[source]] entries")
    return specs


def load_pair(path: Path | str) -> PairConfig:
    """Read one configs/pairs/<id>.toml into a PairConfig."""
    path = Path(path)
    data = _read_toml(path)
    try:
        config = PairConfig(
            id=data["id"],
            source_lang=data["source_lang"],
            target_lang=data["target_lang"],
            name=data.get("name", data["id"]),
            bookname=data.get("bookname", data["id"]),
            tier=int(data.get("tier", 1)),
            description=data.get("description", ""),
            basename=data.get("basename", data["id"]),
        )
    except KeyError as error:
        raise ConfigError(f"{path}: missing required key {error}") from None

    if "pivot" in data:
        raw = data["pivot"]
        try:
            config.pivot = PivotSpec(
                source_side=raw["source_side"],
                target_side=raw["target_side"],
                gloss_providers=list(raw.get("gloss_providers", [])),
                gloss_langs=list(raw.get("gloss_langs", [])),
                keep_gloss_only=bool(raw.get("keep_gloss_only", True)),
                max_translations=int(raw.get("max_translations", 8)),
                max_senses_per_entry=int(raw.get("max_senses_per_entry", 0)),
            )
        except KeyError as error:
            raise ConfigError(f"{path}: [pivot] missing {error}") from None

    for raw in data.get("enrich", ()):
        try:
            config.enrich.append(
                EnrichSpec(
                    source=raw["source"],
                    add_new_headwords=bool(raw.get("add_new_headwords", True)),
                )
            )
        except KeyError as error:
            raise ConfigError(f"{path}: [[enrich]] missing {error}") from None

    raw_inflections = data.get("inflections", {})
    config.inflections = InflectionSpec(
        wordnet_exceptions=raw_inflections.get("wordnet_exceptions", ""),
        rules=bool(raw_inflections.get("rules", False)),
        from_sources=list(raw_inflections.get("from_sources", [])),
        follow_aliases=bool(raw_inflections.get("follow_aliases", False)),
    )

    raw_benchmark = data.get("benchmark", {})
    config.benchmark = BenchmarkSpec(
        frequency_list=raw_benchmark.get("frequency_list", ""),
        frequency_list_name=raw_benchmark.get("frequency_list_name", ""),
    )

    # A pair with neither a pivot nor an enrich source would produce nothing.
    if not config.pivot and not config.enrich:
        raise ConfigError(f"{path}: a pair needs at least a [pivot] or one [[enrich]]")
    return config


def load_all_pairs(directory: Path | str) -> dict[str, PairConfig]:
    """Read every pair config in *directory*, keyed by pair id."""
    pairs: dict[str, PairConfig] = {}
    for path in sorted(Path(directory).glob("*.toml")):
        config = load_pair(path)
        if config.id in pairs:
            raise ConfigError(f"duplicate pair id {config.id!r} in {directory}")
        pairs[config.id] = config
    return pairs
