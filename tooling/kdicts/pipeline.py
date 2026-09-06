"""Build one dictionary end to end.

The steps run in this order:

1. Instantiate every source the pair config names.
2. Pivot: join the two wordnets through their shared synset ids. This defines
   the shape of the dictionary.
3. Enrich: lay Wiktionary entries over the pivot result.
4. Attach inflected forms, so a word can be looked up as it appears in a book.
5. Resolve the outbound licence from the senses actually emitted.
6. Render the entries and write the StarDict files.
7. Measure the result and write metrics.json.
8. Verify by reading the written bytes back with an independent reader.
9. Package the directory into a .zip.
"""

from __future__ import annotations

import random
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .bench.metrics import Metrics, load_frequency_list, measure, write_metrics
from .config import PairConfig
from .ir import Dictionary, Pos
from .licensing import IncompatibleLicenses, resolve_bundle_license
from .merge.enrich import attach_inflections, enrich
from .merge.inflect import english_forms, wordnet_exceptions
from .merge.pivot import PivotConfig, PivotStats, build_pivot
from .package import ifo_description, write_package_files, write_zip
from .sources import SourceSpec, build_source
from .verify.stardict_reader import StarDictReader
from .writers.render import RenderOptions, render_entry
from .writers.stardict import IfoMeta, WriteReport, write_stardict

__all__ = ["BuildError", "BuildResult", "build_pair", "verify_output"]


class BuildError(Exception):
    pass


@dataclass(slots=True)
class BuildResult:
    pair: str
    directory: Path
    report: WriteReport
    metrics: Metrics
    bundle_license_id: str
    #: The downloadable archive, when one was requested.
    archive: Path | None = None
    pivot_stats: PivotStats | None = None
    dropped_sources: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def _instantiate(pair: PairConfig, sources: dict[str, SourceSpec], data_root: Path) -> dict[str, Any]:
    instances: dict[str, Any] = {}
    for source_id in pair.source_ids():
        spec = sources.get(source_id)
        if spec is None:
            raise BuildError(
                f"pair {pair.id!r} references source {source_id!r}, which is not "
                "declared in configs/sources.toml"
            )
        instances[source_id] = build_source(spec, data_root)
    return instances


def _resolve_license(
    dictionary: Dictionary,
    *,
    drop_incompatible: bool,
) -> tuple[str, list[str]]:
    """Decide the bundle licence, or fail loudly.

    ``drop_incompatible`` is opt-in and never the default: silently dropping a
    source changes what the user downloads, so it must be an explicit choice
    recorded in the build log, not a fallback the pipeline reaches for on its
    own.
    """
    try:
        return resolve_bundle_license(dictionary.license_ids).id, []
    except IncompatibleLicenses as error:
        if not drop_incompatible:
            raise BuildError(
                f"{error}\n"
                "Pass --drop-incompatible to build anyway by removing the offending "
                "material, or split this pair into separate bundles. Refusing to emit "
                "a file whose licence cannot be stated."
            ) from error

    # Greedily drop the most restrictive licences until what remains resolves.
    remaining = set(dictionary.license_ids)
    dropped: list[str] = []
    order = sorted(remaining, key=lambda i: (i.startswith("CECILL"), i.startswith("GPL"), i), reverse=True)
    for license_id in order:
        remaining.discard(license_id)
        dropped.append(license_id)
        if not remaining:
            break
        try:
            resolved = resolve_bundle_license(remaining).id
        except IncompatibleLicenses:
            continue
        dictionary.drop_licenses(dropped)
        return resolved, dropped
    raise BuildError("could not find any droppable subset that yields a licensable bundle")


def build_pair(
    pair: PairConfig,
    sources: dict[str, SourceSpec],
    *,
    data_root: Path,
    out_root: Path,
    compress: bool = True,
    drop_incompatible: bool = False,
    verify_sample: int = 500,
    make_archive: bool = True,
) -> BuildResult:
    """Build the dictionary described by *pair*."""
    data_root, out_root = Path(data_root), Path(out_root)
    instances = _instantiate(pair, sources, data_root)
    notes: list[str] = []

    # --- pivot ---------------------------------------------------------------
    dictionary = Dictionary(source_lang=pair.source_lang, target_lang=pair.target_lang)
    pivot_stats: PivotStats | None = None
    if pair.pivot:
        source_side = instances[pair.pivot.source_side]
        target_side = instances[pair.pivot.target_side]
        gloss_providers = [
            (getattr(instances[sid], "lang", "") or pair.target_lang, instances[sid])
            for sid in pair.pivot.gloss_providers
        ]
        dictionary, pivot_stats = build_pivot(
            source_side,
            target_side,
            gloss_providers=gloss_providers,
            config=PivotConfig(
                keep_gloss_only=pair.pivot.keep_gloss_only,
                gloss_langs=tuple(pair.pivot.gloss_langs),
                max_translations=pair.pivot.max_translations,
                max_senses_per_entry=pair.pivot.max_senses_per_entry,
            ),
        )
        notes.append(
            f"pivot: {pivot_stats.entries} entries from {pivot_stats.source_lemmas} source lemmas "
            f"over {pivot_stats.shared_synsets} shared synsets"
        )

    # --- enrichment ----------------------------------------------------------
    for spec in pair.enrich:
        source = instances[spec.source]
        stats = enrich(
            dictionary,
            source.entries(),
            add_new_headwords=spec.add_new_headwords,
        )
        notes.append(
            f"enrich {spec.source}: +{stats.entries_added} entries, "
            f"{stats.entries_extended} extended, +{stats.senses_added} senses"
        )

    if not dictionary.entries:
        raise BuildError(f"pair {pair.id!r} produced no entries; check the source paths")

    # --- inflections ---------------------------------------------------------
    inflection_notes = _attach_all_inflections(pair, instances, dictionary, data_root)
    notes.extend(inflection_notes)

    # --- licence -------------------------------------------------------------
    bundle_license_id, dropped = _resolve_license(dictionary, drop_incompatible=drop_incompatible)
    if dropped:
        notes.append(f"dropped material licensed under: {', '.join(dropped)}")

    credits: dict[str, str] = {}
    for source_id, instance in instances.items():
        spec = instance.spec
        credits[source_id] = spec.credit or spec.url or spec.id

    # --- render and write ----------------------------------------------------
    options = RenderOptions(target_lang=pair.target_lang)
    rendered: list[tuple[str, str]] = []
    synonyms: list[tuple[str, str]] = []
    for entry in dictionary:
        body = render_entry(entry, options)
        if not body:
            continue
        rendered.append((entry.headword, body))
        synonyms.extend((form, entry.headword) for form in entry.forms)

    meta = IfoMeta(
        bookname=pair.bookname,
        author="koreader-dicts",
        website="https://github.com/koreader-dicts",
        date=datetime.now(UTC).strftime("%Y.%m.%d"),
        description=ifo_description(
            name=pair.name,
            bundle_license_id=bundle_license_id,
            source_credits=credits,
            entries=len(rendered),
            forms=dictionary.form_count,
        ),
        sametypesequence="h",
    )
    report = write_stardict(
        out_root / pair.id,
        pair.basename,
        rendered,
        meta,
        synonyms=synonyms,
        compress=compress,
    )
    if report.skipped:
        notes.append(f"writer skipped {len(report.skipped)} inputs (see build log)")

    write_package_files(
        report.directory,
        name=pair.name,
        basename=pair.basename,
        license_ids=dictionary.license_ids,
        source_credits=credits,
        entries=report.wordcount,
        forms=report.synwordcount,
    )

    # --- metrics -------------------------------------------------------------
    frequency_words: list[str] = []
    if pair.benchmark.frequency_list:
        frequency_path = data_root / pair.benchmark.frequency_list
        if frequency_path.exists():
            frequency_words = load_frequency_list(frequency_path, limit=max(_cutoffs()))
        else:
            notes.append(f"frequency list {frequency_path} missing; coverage not measured")

    metrics = measure(
        dictionary,
        frequency_words=frequency_words,
        frequency_list_name=pair.benchmark.frequency_list_name or pair.benchmark.frequency_list,
        bundle_license=bundle_license_id,
        sources=[
            {
                "id": source_id,
                "kind": instance.spec.kind,
                "license": getattr(instance, "license_id", instance.spec.license_id),
                "credit": credits[source_id],
                "url": instance.spec.url,
            }
            for source_id, instance in sorted(instances.items())
        ],
    )
    write_metrics(metrics, out_root / pair.id / "metrics.json")

    # --- verify --------------------------------------------------------------
    if verify_sample:
        failures = verify_output(report.directory, sample=verify_sample)
        if failures:
            raise BuildError(
                f"pair {pair.id!r}: {len(failures)} of {verify_sample} sampled headwords "
                f"could not be found by binary search in the file we just wrote. "
                f"First few: {failures[:5]}"
            )
        notes.append(f"verified {verify_sample} sampled lookups against the written files")

    # Zipped only after verification passes, so a bad build never produces
    # something that looks ready to publish.
    archive: Path | None = None
    if make_archive:
        archive = write_zip(report.directory)
        notes.append(f"packaged {archive.name} ({archive.stat().st_size / 1e6:.1f} MB)")

    return BuildResult(
        pair=pair.id,
        directory=report.directory,
        report=report,
        metrics=metrics,
        bundle_license_id=bundle_license_id,
        archive=archive,
        pivot_stats=pivot_stats,
        dropped_sources=dropped,
        notes=notes,
    )


def _cutoffs() -> tuple[int, ...]:
    from .bench.metrics import COVERAGE_CUTOFFS

    return COVERAGE_CUTOFFS


def _attach_all_inflections(
    pair: PairConfig,
    instances: dict[str, Any],
    dictionary: Dictionary,
    data_root: Path,
) -> list[str]:
    notes: list[str] = []
    spec = pair.inflections

    if spec.wordnet_exceptions:
        source = instances.get(spec.wordnet_exceptions)
        if source is not None:
            added = attach_inflections(dictionary, wordnet_exceptions(source.root))
            notes.append(f"inflections: +{added} from WordNet exception files")

    for source_id in spec.from_sources:
        source = instances.get(source_id)
        streamer = getattr(source, "inflections", None)
        if callable(streamer):
            added = attach_inflections(dictionary, streamer())
            notes.append(f"inflections: +{added} from {source_id}")

    if spec.rules:
        added = 0
        for entry in dictionary:
            parts_of_speech = {sense.pos for sense in entry.senses}
            generated: set[str] = set()
            for pos in parts_of_speech:
                if pos in (Pos.NOUN, Pos.VERB, Pos.ADJ, Pos.ADV):
                    generated |= english_forms(entry.headword, pos)
            generated -= entry.forms
            generated.discard(entry.headword)
            entry.forms |= generated
            added += len(generated)
        notes.append(f"inflections: +{added} from morphological rules")

    return notes


def verify_output(directory: Path | str, *, sample: int = 500, seed: int = 0) -> list[str]:
    """Binary-search a sample of the written headwords. Returns the failures.

    This is the check that a dictionary is actually usable: it parses the files
    back with a reader that transcribes StarDict's own comparator rather than
    reusing the writer's sort key, so a wrong collation shows up as a lookup
    miss here instead of on someone's Kindle.
    """
    failures: list[str] = []
    with StarDictReader(directory) as reader:
        if not reader.entries:
            return ["<dictionary is empty>"]
        rng = random.Random(seed)
        indices = range(len(reader.entries))
        chosen = [
            reader.entries[i].word.decode("utf-8")
            for i in (indices if len(reader.entries) <= sample else rng.sample(indices, sample))
        ]
        for word in chosen:
            hits = reader.find_idx(word)
            if not hits:
                failures.append(word)
                continue
            if not reader.definition_at(hits[0]):
                failures.append(word)

        # Also confirm the .syn file resolves, since it is the half that is
        # easiest to get wrong and impossible to notice without checking.
        if reader.synonyms:
            syn_indices = range(len(reader.synonyms))
            picked = (
                syn_indices if len(reader.synonyms) <= sample
                else rng.sample(syn_indices, sample)
            )
            for form in (reader.synonyms[i][0].decode("utf-8") for i in picked):
                if not reader.find_syn(form):
                    failures.append(f"<syn> {form}")
    return failures


def sample_lookups(directory: Path | str, words: Sequence[str]) -> dict[str, str]:
    """Look up specific words in a built dictionary. Used by the CLI and by eyes."""
    out: dict[str, str] = {}
    with StarDictReader(directory) as reader:
        for word in words:
            found = reader.lookup(word)
            out[word] = found[0] if found else ""
    return out
