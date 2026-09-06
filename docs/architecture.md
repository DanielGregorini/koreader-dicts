# Architecture

Two halves, joined by a JSON file. For a plain-language walkthrough of a single
build, read [build-process.md](build-process.md) first; this file covers the
structure behind it.

```
sources ──▶ adapters ──▶ IR ──▶ pivot ──▶ enrich ──▶ writer ──▶ StarDict
                                                        │
                                                        ├──▶ metrics.json ──▶ web/
                                                        └──▶ verify (binary search)
```

The Python toolchain produces dictionaries and `metrics.json`. The Next.js site
reads `catalog.json` and renders it. The site computes nothing.

## The internal representation

Everything normalises into `kdicts.ir`. Three decisions shape it:

**Senses are synset-anchored.** `Sense.synset` holds a Princeton WordNet 3.0
synset id (`02084071-n`). It is the join key that makes the pivot work. Senses
with no synset — a Wiktionary sense with no wordnet counterpart — are still
first class; they just cannot pivot, and only arrive through a direct bilingual
source.

**Provenance is per sense, not per dictionary.** Licence compatibility is
decided from the licences actually present in the emitted senses. A source that
contributed nothing to a pair does not constrain its licence, and dropping an
incompatible source removes exactly the senses it touched.

**Merging is additive.** `Entry.absorb` collapses duplicate senses by synset (or
by normalised gloss, for unanchored ones), unions translations preserving
first-seen order, and accumulates provenance. Enrichment never overwrites pivot
output; a sense that picked up a Wiktionary translation now carries the
Wiktionary licence too, and the bundler sees it.

### Canonical synset ids

`canonical_synset(offset, tag)` folds adjective satellites (`s`) onto `a`.

Princeton WordNet distinguishes head adjectives from satellites, but OMW 1.4
writes both as `-a`: the synset whose `data.adj` line says `s` at offset
`00003553` is `omw-pt-00003553-a` in the Portuguese lexicon. Keeping the
distinction would make roughly 18k synsets — a large share of all adjectives —
fail to pivot. Folding is lossless: the offset is a byte offset into `data.adj`
and is already unique across both types.

Older `.tab` distributions spell satellites `-s`, so the `omw-tab` adapter
canonicalises too and the two formats can be mixed in one build.

## The pivot

`kdicts.merge.pivot.build_pivot(source_side, target_side, ...)`:

1. Build `synset → ordered target lemmas` from the target side.
2. Build `lemma → [(rank, synset)]` from the source side.
3. For each source lemma, emit one sense per synset, with the target lemmas as
   translations and a gloss from the best available provider.

Direction is just argument order: `pt-en` is `build_pivot(omw_pt, pwn30)`. A
pair with no English on either side (`es-pt`) is `build_pivot(omw_es, omw_pt)`.
Neither side knows the other exists.

Gloss providers are consulted in a configured language preference, so a
Portuguese reader gets a Portuguese definition where one exists and falls back
to the English WordNet gloss where it does not. In practice most OMW lexicons
carry no definitions at all — only about a third of the 32 in 1.4 do, and
OpenWN-PT is not among them — which is why the fallback matters.

### Gloss-only senses

When the source wordnet knows a concept the target language has no word for, the
sense has a definition and no translation. Those are kept by default, because a
definition still helps a reader, and they are counted separately in every
metric rather than added to the translation total.

## Enrichment

Direct bilingual sources are layered over the pivot, never used in its place.
They supply what wordnets lack: slang, idiom, proper nouns, recent vocabulary
and inflected forms.

The kaikki adapter has two modes because the two useful shapes of Wiktionary
data are different:

- `translations` reads the source language's own edition and harvests
  translation tables. Wide, shallow. Note that wiktextract puts most
  translations on `senses[].translations`, not on the page-level
  `translations` — reading only the latter silently discards the majority of
  the data.
- `foreign_entries` reads the *target* language's edition and keeps pages
  describing source-language words: English words defined in Portuguese by
  Portuguese speakers. Much better prose, far fewer headwords.

## Inflections

The `.syn` file is what makes a dictionary usable while reading. Three sources,
in descending order of trustworthiness:

1. WordNet's exception files (`noun.exc`, `verb.exc`, …) — hand-curated
   irregulars, *went → go*, *geese → goose*. These ship in the full
   `WordNet-3.0.tar.gz`, **not** in `WNdb-3.0.tar.gz`.
2. Wiktionary form tables.
3. Rule-based morphology, as the backstop.

The rules over-generate slightly. A spurious form costs a few bytes and is only
ever hit by selecting a non-word; a missing form costs a failed lookup mid-book.

## Licence resolution

`kdicts.licensing` models a directed relicensing relation: each licence lists the
licences its material may be redistributed under. A set is compatible iff the
intersection of those sets is non-empty, and the bundle takes the **least**
restrictive member — permissive input stays permissive.

Resolution runs *after* the pivot and enrichment, against the licences in the
emitted senses. When no lawful outbound licence exists the build fails. Dropping
the offending material is possible but opt-in (`--drop-incompatible`) and
recorded in the build log, because it silently changes what a user downloads.

## Verification

`kdicts.verify.stardict_reader` re-implements StarDict's `stardict_strcmp` and
glib's `g_ascii_strcasecmp` from the C, and does not import the writer's sort
key. Every build binary-searches a sample of what it just wrote. A check that
reused the writer's own key would agree with the writer even when the writer is
wrong, so the two implementations are kept separate.
