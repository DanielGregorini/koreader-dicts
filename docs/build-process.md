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

Three shapes of Wiktionary data are read, because they are useful for different
reasons:

- **Translation tables** from the source language's own edition. Wide coverage,
  thin definitions.
- **Foreign-word entries** from the target language's edition — English words
  described in Portuguese, by Portuguese speakers. Far fewer headwords, much
  better prose.
- **Own-language entries**, which is what a monolingual dictionary is made of:
  the pages an edition writes about its own language. Nothing is translated, so
  the gloss stays a definition and the entry's synonym lists are read as
  synonyms.

For a monolingual pair there is usually no step 2 at all — the wordnets carry
almost no definitions outside English, so there is nothing to pivot for and
this step is the whole dictionary. English is the exception: pivoting WordNet
against itself gives the synonym set and the definition that was already
written for it. Arabic is the other way round: it has a wordnet and no
Wiktionary edition, so `ar-ar` is a pivot with no definitions at all — a
thesaurus, each entry a synonym set and nothing more.

## 4. Attach inflected forms

A reader taps *wielded* in a novel. The headword is *wield*. Without a mapping
between the two, the lookup fails.

Forms come from three places, most reliable first:

1. WordNet's exception files, which list irregulars by hand: *went → go*,
   *geese → goose*.
2. Wiktionary's form tables.
3. Rule-based morphology, as a backstop for everything the first two missed.

Headwords and forms are normalised to what a reader can actually tap. That
means collapsing whitespace, and stripping the marks running text never
carries: Cyrillic stress (*соба́ки*) and Arabic vocalization (*كَلْب*), which
the wordnets and Wiktionary write and books do not. Translations and synonyms
keep those marks, because on the display side they help — a learner reading
English to Arabic wants the vowels — and nothing is ever looked up by a
translation. Stripping does create homographs: *كِلَاب* (dogs) and *كُلَّاب*
(hook) both become *كلاب*, and a lookup returns both entries, which is how
printed Arabic works too.

A form whose headword is not in the dictionary is discarded here, so the number
reported in the metrics is the number that will really reach the file. A pair
can opt to follow aliases instead — a lemma that is itself a form of exactly
one headword counts as that headword — which Japanese needs, because its
edition keeps lemma pages in kana and makes the kanji spelling a pointer. It
stays off elsewhere: aliases chain through homographs, and *went* ended up on
*gin*. Two kinds of form are dropped on purpose: forms of more than one word, which a
reader tapping a single word can never reach, and possessive-suffixed forms.
Finnish is why: its tables list six possessive paradigms on top of the thirty
case forms, 21 of the 26 million forms they yield, and measured against the top
50k Finnish words they reach 3,494 more at five times the index. An index a
Kindle cannot hold reaches nothing.

The build also refuses an index that no reader can reach: if forms were
attached and not one of the words in the frequency list resolves through the
inflection index, the build fails. Russian once shipped 731k forms, every one
carrying a stress mark that no book contains, and every check passed.

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

The order of the senses is the part of this step that matters. On a six-inch
screen the reader sees the first two lines and nothing else, so that is the
whole lookup. Senses with a translation come first. Among those, a sense that
two sources agree on — a wordnet sense whose equivalents also appear under one
of the entry's Wiktionary senses — comes before one only the wordnet lists.
Then corpus frequency decides: WordNet's own tag counts on the English side,
and the same counts summed per synset for every other language, since a
concept's frequency transfers to any word mapped onto it. The lexicon's own
listing order is the last resort.

The order of those two rules depends on whose frequency it is. A borrowed
synset total says the concept is common, not that this word for it is, so
there agreement comes first. When the source side is WordNet, every sense
carries its own count, and that count comes first; agreement only breaks
the ties — which are many, since most senses were never tagged. Otherwise
*apply* opens on "apply to a surface", because Wiktionary happens to agree
with it, over "put into service", tagged thirty times.

Agreement is the rule that keeps *patata* from opening on the vulgar sense.
The Spanish lexicon maps the word onto that synset, and the synset is common
in English as an ordinary anatomical word, but the Spanish Wiktionary does not
know the sense at all. It is also what keeps *ذهبت* (she went) from opening on
*be*: the Arabic WordNet maps the word onto the *be* synsets too, and nothing
in English is tagged more often. For English verbs the comparison ignores the
infinitive marker — Wiktionary writes "to go", WordNet "go" — or no verb sense
would ever agree.

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
