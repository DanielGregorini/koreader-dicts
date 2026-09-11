"""``kdicts`` command line.

    kdicts sources                 what is declared, and what is on disk
    kdicts fetch [id ...]          download and unpack source data
    kdicts build <pair|all>        generate dictionaries
    kdicts verify <directory>      binary-search a built dictionary
    kdicts lookup <directory> word look a word up, as a device would
    kdicts catalog                 write the JSON the website renders
    kdicts koreader                write the entries for KOReader's download list
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from .config import ConfigError, load_all_pairs, load_sources
from .fetch import FetchError, ensure_source
from .koreader_list import render_koreader_list
from .package import write_catalog
from .pipeline import BuildError, build_pair, sample_lookups, verify_output
from .sources import REGISTRY, SourceError, SourceSpec, build_source

__all__ = ["main"]

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_CONFIGS = _REPO_ROOT / "configs"
_DEFAULT_DATA = _REPO_ROOT / "data"
# Named for what it contains, not for what produced it: this is the folder a
# user opens to find dictionaries, so it is not called "build".
_DEFAULT_OUTPUT = _REPO_ROOT / "dictionaries"


def _add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--configs", type=Path, default=_DEFAULT_CONFIGS, help="config directory")
    parser.add_argument("--data", type=Path, default=_DEFAULT_DATA, help="data root (never in git)")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="kdicts", description=__doc__.splitlines()[0])
    subparsers = parser.add_subparsers(dest="command", required=True)

    sources = subparsers.add_parser("sources", help="list declared sources and their state")
    _add_common(sources)
    sources.add_argument(
        "--verify",
        action="store_true",
        help="open each file that is present and check it is the edition the config says",
    )

    fetch = subparsers.add_parser("fetch", help="download source data")
    _add_common(fetch)
    fetch.add_argument("ids", nargs="*", help="source ids; default is all of them")
    fetch.add_argument("--pair", action="append", default=[], help="every source a pair needs")
    fetch.add_argument("--force", action="store_true", help="re-download even if present")

    build = subparsers.add_parser("build", help="generate dictionaries")
    _add_common(build)
    build.add_argument("pairs", nargs="*", default=["all"], help="pair ids, or 'all'")
    build.add_argument("--out", type=Path, default=_DEFAULT_OUTPUT)
    build.add_argument("--no-compress", action="store_true", help="write .dict instead of .dict.dz")
    build.add_argument(
        "--drop-incompatible",
        action="store_true",
        help="drop material whose licence cannot be bundled, instead of failing",
    )
    build.add_argument("--verify-sample", type=int, default=500)
    build.add_argument(
        "--no-zip", action="store_true", help="skip the downloadable .zip archive"
    )

    verify = subparsers.add_parser("verify", help="binary-search a built dictionary")
    verify.add_argument("directory", type=Path)
    verify.add_argument("--sample", type=int, default=1000)

    lookup = subparsers.add_parser("lookup", help="look words up in a built dictionary")
    lookup.add_argument("directory", type=Path)
    lookup.add_argument("words", nargs="+")

    catalog = subparsers.add_parser("catalog", help="write the catalog JSON for the website")
    _add_common(catalog)
    catalog.add_argument("--out", type=Path, default=_DEFAULT_OUTPUT)
    catalog.add_argument("--catalog-path", type=Path, default=None)

    koreader = subparsers.add_parser(
        "koreader", help="write the Lua entries for KOReader's built-in dictionary list"
    )
    _add_common(koreader)
    koreader.add_argument("--catalog-path", type=Path, default=_DEFAULT_OUTPUT / "catalog.json")
    koreader.add_argument("--out", type=Path, default=None, help="write here instead of stdout")
    koreader.add_argument(
        "--min-coverage", type=float, default=60.0, help="leave out pairs measured below this"
    )
    koreader.add_argument("--exclude", nargs="*", default=[], help="pair ids to leave out")
    koreader.add_argument(
        "--releases-base",
        default="https://github.com/DanielGregorini/koreader-dicts/releases/latest/download",
    )

    return parser


# -- commands -----------------------------------------------------------------


def _cmd_sources(args: argparse.Namespace) -> int:
    specs = load_sources(args.configs / "sources.toml")
    failures = 0
    for spec in specs.values():
        target = args.data / spec.path
        state = "present" if target.exists() else "MISSING"
        pinned = "pinned" if spec.sha256 else "unpinned"
        print(f"{spec.id:<18} {spec.kind:<10} {spec.license_id or '?':<18} {state:<8} {pinned}")
        print(f"{'':<18} {target}")
        if args.verify and target.exists():
            problem = _verify_source(spec, args.data)
            if problem:
                print(f"{'':<18} FAILED: {problem}", file=sys.stderr)
                failures += 1
            else:
                print(f"{'':<18} verified")
    return 1 if failures else 0


def _verify_source(spec: SourceSpec, data_root: Path) -> str:
    """Empty when the file behind *spec* is what the config claims, else why not.

    Six Wiktionary editions once arrived as six copies of the Spanish one, and
    every adapter opened them without complaint: the format was right, only
    the language was wrong. Opening the adapter catches a bad licence header;
    this catches a bad file.
    """
    if spec.kind not in REGISTRY:
        # Benchmark inputs have no adapter; there is nothing to open.
        return ""
    try:
        source = build_source(spec, data_root)
    except SourceError as error:
        return str(error)
    if spec.kind == "kaikki":
        lang = str(spec.options.get("source_lang") or spec.lang)
        found, read = source.count_pages(lang)
        if not found:
            return f"no page in {read} has lang_code {lang!r}; wrong edition behind this path?"
    return ""


def _cmd_fetch(args: argparse.Namespace) -> int:
    specs = load_sources(args.configs / "sources.toml")
    wanted = list(args.ids)
    if args.pair:
        pairs = load_all_pairs(args.configs / "pairs")
        for pair_id in args.pair:
            pair = pairs.get(pair_id)
            if pair is None:
                print(f"unknown pair {pair_id!r}", file=sys.stderr)
                return 1
            wanted += [i for i in pair.source_ids() if i not in wanted]
            # The benchmark names a file, not a source; find the source that
            # provides it so the coverage table is measured on a fresh runner.
            wanted += [
                spec.id
                for spec in specs.values()
                if spec.path == pair.benchmark.frequency_list and spec.id not in wanted
            ]
    if not wanted:
        wanted = list(specs)
    failures = 0
    for source_id in wanted:
        spec = specs.get(source_id)
        if spec is None:
            print(f"unknown source {source_id!r}", file=sys.stderr)
            failures += 1
            continue
        if not spec.url:
            print(f"{source_id}: no url declared, skipping", file=sys.stderr)
            continue
        try:
            path = ensure_source(
                url=spec.url,
                data_root=args.data,
                relative_path=spec.path,
                sha256=spec.sha256,
                archive_member=spec.archive_member,
                force=args.force,
            )
        except FetchError as error:
            print(f"{source_id}: {error}", file=sys.stderr)
            failures += 1
            continue
        print(f"{source_id}: {path}")
    return 1 if failures else 0


def _cmd_build(args: argparse.Namespace) -> int:
    specs = load_sources(args.configs / "sources.toml")
    pairs = load_all_pairs(args.configs / "pairs")
    wanted = list(pairs) if args.pairs == ["all"] or "all" in args.pairs else args.pairs

    failures = 0
    for pair_id in wanted:
        pair = pairs.get(pair_id)
        if pair is None:
            print(f"unknown pair {pair_id!r}", file=sys.stderr)
            failures += 1
            continue
        print(f"== {pair.id}: {pair.name}")
        try:
            result = build_pair(
                pair,
                specs,
                data_root=args.data,
                out_root=args.out,
                compress=not args.no_compress,
                drop_incompatible=args.drop_incompatible,
                verify_sample=args.verify_sample,
                make_archive=not args.no_zip,
            )
        except (BuildError, SourceError, ConfigError) as error:
            print(f"   FAILED: {error}", file=sys.stderr)
            failures += 1
            continue
        for note in result.notes:
            print(f"   {note}")
        print(
            f"   wrote {result.report.wordcount} entries, "
            f"{result.report.synwordcount} inflected forms, "
            f"licence {result.bundle_license_id}"
        )
        print(f"   -> {result.directory}")
        if result.archive:
            print(f"   -> {result.archive} ({result.archive.stat().st_size / 1e6:.1f} MB)")
    return 1 if failures else 0


def _cmd_verify(args: argparse.Namespace) -> int:
    failures = verify_output(args.directory, sample=args.sample)
    if failures:
        print(f"{len(failures)} lookups failed. First few: {failures[:10]}", file=sys.stderr)
        return 1
    print(f"{args.directory}: all sampled lookups resolved")
    return 0


def _cmd_lookup(args: argparse.Namespace) -> int:
    results = sample_lookups(args.directory, args.words)
    missing = 0
    for word, body in results.items():
        if body:
            print(f"{word}\n  {body}\n")
        else:
            missing += 1
            print(f"{word}\n  <not found>\n")
    return 1 if missing else 0


def _cmd_catalog(args: argparse.Namespace) -> int:
    pairs = load_all_pairs(args.configs / "pairs")
    entries: list[dict[str, object]] = []
    for pair in pairs.values():
        metrics_path = args.out / pair.id / "metrics.json"
        archive_path = args.out / pair.id / f"{pair.basename}.zip"
        record: dict[str, object] = {
            "pair": pair.id,
            "name": pair.name,
            "source_lang": pair.source_lang,
            "target_lang": pair.target_lang,
            "tier": pair.tier,
            "description": pair.description,
            "basename": pair.basename,
            "built": metrics_path.exists(),
            # The real size of the file a reader will download. The site shows
            # this; it must never be estimated.
            "archive_bytes": archive_path.stat().st_size if archive_path.exists() else 0,
        }
        if metrics_path.exists():
            record["metrics"] = json.loads(metrics_path.read_text(encoding="utf-8"))
        entries.append(record)
    path = args.catalog_path or (args.out / "catalog.json")
    write_catalog(path, entries)
    built = sum(1 for e in entries if e["built"])
    print(f"{path}: {len(entries)} pairs, {built} built")
    return 0


def _cmd_koreader(args: argparse.Namespace) -> int:
    pairs = load_all_pairs(args.configs / "pairs")
    lua, listed = render_koreader_list(
        args.catalog_path,
        pairs,
        releases_base=args.releases_base,
        min_coverage=args.min_coverage,
        exclude=args.exclude,
    )
    if args.out:
        args.out.write_text(lua, encoding="utf-8")
        print(f"{args.out}: {len(listed)} dictionaries")
    else:
        print(lua, end="")
    return 0


_COMMANDS = {
    "sources": _cmd_sources,
    "fetch": _cmd_fetch,
    "build": _cmd_build,
    "verify": _cmd_verify,
    "lookup": _cmd_lookup,
    "catalog": _cmd_catalog,
    "koreader": _cmd_koreader,
}


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return _COMMANDS[args.command](args)
    except (ConfigError, SourceError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
