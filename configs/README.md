# configs/

The whole definition of what gets built. Nothing here is code, and adding a
dictionary does not require touching Python.

## `sources.toml`

One `[[source]]` block per data source. Each block says where the file comes
from, where it lands on disk, which adapter reads it, what licence it carries,
and its SHA-256 checksum.

The checksum is the important field. Upstream files are republished without
warning, and a build that silently used changed data would produce a dictionary
nobody could account for. If the checksum does not match, `kdicts fetch` stops
and says so.

## `pairs/*.toml`

One file per dictionary, named after the pair id: `en-pt.toml` produces
`en-pt`. A pair file names sources by their id in `sources.toml` and says how to
combine them:

- `[pivot]` — the two wordnets to join through shared synset ids. This produces
  most of the dictionary. A pair can leave it out and be built from `[[enrich]]`
  alone, which is what the pairs with no wordnet behind them do.
- `[[enrich]]` — sources laid on top, usually Wiktionary. Monolingual pairs are
  made of nothing else.
- `[inflections]` — where inflected forms come from.
- `[benchmark]` — the frequency list to measure coverage against.

If both languages already have a wordnet declared in `sources.toml`, a new pair
is one file here and no new code. `docs/adding-a-pair.md` walks through it.
