# How a dictionary gets built

This walks through what actually happens when you run:

```bash
kdicts build en-pt
```

Nine steps, in order. Each one is a module under `tooling/kdicts/`, and the
whole sequence lives in `pipeline.py`.

## 1. Read the configuration

`configs/pairs/en-pt.toml` says which sources to use and how to combine them.
`configs/sources.toml` says where each of those sources comes from and what
licence it carries. Nothing about a language pair is written in Python — the
config files are the whole definition.

The pair file lists its sources by id. Those ids are looked up in the sources
file, and each one is turned into an adapter object that knows how to read that
particular file format.

## 2. Pivot the two wordnets

This is where most of the dictionary comes from.

A wordnet groups words by meaning. Each group of synonyms — a *synset* — has an
identifying number. The important part is that every wordnet in the Open
Multilingual Wordnet reuses the numbers from Princeton WordNet, so the same
concept carries the same number in every language.

That means a bilingual dictionary between any two mapped languages already
exists implicitly:

```
"wield"  →  01095899-v  →  "empunhar", "manejar"
```

The English WordNet says *wield* belongs to synset `01095899-v`. The Portuguese
wordnet says `01095899-v` contains *empunhar* and *manejar*. Joining on the
number gives the translation, and no English-Portuguese resource was consulted
to get it.

The code builds two lookup tables — synset to target words, and source word to
synsets — and then walks the source words, emitting one sense per synset.

Direction is only argument order. `pt-en` swaps the two sides. `es-pt` uses two
non-English wordnets and works exactly the same way.

**Where the concept has no word.** Sometimes the source wordnet knows a concept
and the target language has no single word for it. That sense ends up with a
definition and no translation. It is kept, because a definition still helps a
reader, and it is counted on its own line in the metrics rather than folded
into the translation count.

## 3. Lay Wiktionary over the result

Wordnets are frozen and formal. They carry no slang, no idiom, nothing coined
recently, and no inflected forms. Wiktionary has all of those, so it is merged
on top of the pivot result.

Merging is additive. When a Wiktionary entry matches a headword the pivot
already produced, its translations are added to the existing entry rather than
replacing it, and the entry records that it now contains Wiktionary material —
which matters at step 5.

Two shapes of Wiktionary data are read, because they are useful for different
reasons:

- **Translation tables** from the source language's own edition. Wide coverage,
  thin definitions.
- **Foreign-word entries** from the target language's edition — English words
  described in Portuguese, by Portuguese speakers. Far fewer headwords, much
  better prose.

## 4. Attach inflected forms

A reader taps *wielded* in a novel. The headword is *wield*. Without a mapping
between the two, the lookup fails.

Forms come from three places, most reliable first:

1. WordNet's exception files, which list irregulars by hand: *went → go*,
   *geese → goose*.
2. Wiktionary's form tables.
3. Rule-based morphology, as a backstop for everything the first two missed.

A form whose headword is not in the dictionary is discarded here, so the number
reported in the metrics is the number that will really reach the file.

## 5. Decide the licence

Every sense carries the licence of the source it came from. Once the merging is
done, the set of licences actually present is known.

Redistribution is only lawful if there is a single licence that all of them
permit their material to be released under. The code models this as a directed
relation — each licence lists what it can be redistributed as — and intersects
those lists. If the intersection is empty, the build stops. It does not guess,
and it does not quietly drop the offending source unless asked to with
`--drop-incompatible`, which is recorded in the build log.

This runs after merging rather than before, so a source that contributed
nothing to this particular pair does not constrain the outcome.

## 6. Render the entries

Each entry becomes the HTML body KOReader will display: the part of speech,
the translations, the definition, and the example sentence where one exists.

## 7. Write the StarDict files

Four files come out:

| file | contents |
|---|---|
| `.ifo` | metadata: name, entry count, licence, attribution |
| `.idx` | one record per headword: the word, plus where its body starts and how long it is |
| `.dict.dz` | the bodies, compressed so any one of them can be read without decompressing the rest |
| `.syn` | the inflected forms, each pointing at a headword |

The `.idx` is read by binary search, so its sort order is part of the file
format rather than a matter of taste. The order is defined by a specific C
comparator in StarDict, transcribed in `collation.py`. Getting it wrong does
not produce an error — it produces a dictionary that reports "not found" for
words that are physically present in the file.

## 8. Measure

Entry counts, sense counts, how many entries have a real translation versus a
definition only, and coverage against a frequency list, counting inflected
forms. All of it is written to `metrics.json`.

Coverage is the number worth reading: it says what share of the words a reader
actually meets on a page can be resolved.

## 9. Verify, then package

The files that were just written are read back and binary-searched, using a
reader that does not share any code with the writer. A sample of headwords is
looked up the way the device would look them up. Only if that passes is the
directory zipped for download.

An independent reader is the point. A check that reused the writer's own sort
key would agree with the writer even when the writer is wrong.
