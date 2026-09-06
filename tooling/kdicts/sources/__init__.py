"""Source adapter registry.

The core never imports a concrete adapter. Adding a source means writing one
module and registering it here. Adding a language pair means editing a config
file only.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from .base import BilingualSource, LemmaRecord, SourceError, SourceSpec, SynsetRecord, SynsetSource
from .kaikki import KaikkiSource
from .omw import OmwTabSource
from .omw_lmf import OmwLmfSource
from .wordnet import WordNetSource

__all__ = [
    "REGISTRY",
    "BilingualSource",
    "KaikkiSource",
    "LemmaRecord",
    "OmwLmfSource",
    "OmwTabSource",
    "SourceError",
    "SourceSpec",
    "SynsetRecord",
    "SynsetSource",
    "WordNetSource",
    "build_source",
]

# Maps the "kind" field in configs/sources.toml to the adapter that reads it.
REGISTRY: dict[str, Callable[[SourceSpec, Path], Any]] = {
    "wordnet": WordNetSource,
    "omw-tab": OmwTabSource,
    "omw-lmf": OmwLmfSource,
    "kaikki": KaikkiSource,
}


def build_source(spec: SourceSpec, data_root: Path) -> Any:
    """Instantiate the adapter named by ``spec.kind``."""
    try:
        factory = REGISTRY[spec.kind]
    except KeyError:
        raise SourceError(
            f"source {spec.id!r}: unknown kind {spec.kind!r}. Known kinds: "
            + ", ".join(sorted(REGISTRY))
        ) from None
    return factory(spec, Path(data_root) / spec.path)
