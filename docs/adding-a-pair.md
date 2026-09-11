# Adding a language pair, or a source

## A new pair

If both languages already have a source declared in `configs/sources.toml`, a
pair is one file and no code.

```toml
# configs/pairs/en-it.toml
id = "en-it"
source_lang = "en"
target_lang = "it"
tier = 1
name = "English to Italian"
bookname = "en-it"
basename = "en-it"

[pivot]
source_side = "pwn30"
target_side = "omw-it"
gloss_providers = ["omw-it", "pwn30"]   # target language first
gloss_langs = ["it", "en"]
keep_gloss_only = true

[inflections]
wordnet_exceptions = "pwn30"
rules = true

[benchmark]
frequency_list = "freq/en_50k.txt"
```

```bash
kdicts fetch --pair en-it
kdicts sources --verify
kdicts build en-it
```

`--verify` opens every file on disk and checks it is the edition the config
says. Six Wiktionary editions once arrived as six copies of the Spanish one,
and every adapter read them without complaint.

The monthly workflow picks up new pairs automatically; nothing in it needs
editing. It skips any pair that reads the 500 MB English Wiktionary dump, so
those are built by hand.

### Reverse direction

Swap `source_side` and `target_side`. That is the whole change.

### A pair with no English on either side

Also just config — `configs/pairs/es-pt.toml` is the worked example. Neither
side needs to know the other exists; they meet at the synset ids.

Note what you lose: inflected forms. The rule-based inflector is English-only,
so a pivot-only pair like `es-pt` ships with an empty `.syn`. That is visible in
the metrics, and it is the honest state of the pair rather than something to
paper over.

It is fixable per pair, and `it-en` shows how: kaikki publishes one file per
language section of the English Wiktionary, and its form tables give a foreign
headword an inflection index that no English rule could produce. Declare that
file as a `foreign_entries` source and list it under `[inflections]
from_sources`.

### A monolingual pair

`source_lang` and `target_lang` are the same code. Declare the edition with
`mode = "definitions"` and enrich from it: the reader stops guessing that a
short gloss is an equivalent, and reads the page's synonym lists instead.

`en-en` is the one that also gets a `[pivot]`, because pivoting WordNet against
itself is meaningful — the synset *is* the synonym set. The pivot drops a word
from its own synset so nothing is listed as its own synonym. Elsewhere the
wordnets carry no definitions, so there is nothing to pivot for.

List the English edition's section for the language under `[inflections]
from_sources` too. Form tables are language-internal whatever the gloss
language, and the English edition's are often fuller than the edition's own:
the Japanese edition has no conjugation tables at all.

Japanese needs one more thing, `follow_aliases = true`. Its edition keeps the
lemma page under the kana spelling and makes the kanji page a pointer, so the
headword is はしる and 走る is only a form of it — while the English edition's
tables call 走った a form of 走る. Following the alias is what joins them. It is
off everywhere else on purpose: in English, Wiktionary calls *went* a form of
the obsolete *gan*, and *gan* is a form of *gang*, *gin* and *go*, so following
aliases put a liquor at the top of *went*.

## A new source

One adapter module, one line in `tooling/kdicts/sources/__init__.py`. The core
never imports a concrete adapter.

Implement either shape:

- **`SynsetSource`** — `lemmas()` yielding `LemmaRecord(lemma, synset, rank)`
  and `synsets()` yielding `SynsetRecord`. Optionally `synset_members()` for a
  faster reverse mapping. These can generate new pairs.
- **`BilingualSource`** — `entries()` yielding `Entry`. These enrich existing
  pairs and cannot generate one.

### Licence handling is not optional

An adapter must determine its licence from the data, not assume one:

- Parse whatever the source declares (`<Lexicon license="...">`, a `.tab`
  header comment) and map it with `kdicts.sources.omw.detect_license`.
- If config declares a licence and the file says something else, **raise** —
  that means upstream changed terms under a dictionary we already published.
- If nothing can be determined and config does not declare one, **raise**.
  `UNKNOWN` is modelled as an excluded licence precisely so that guessing is
  impossible.

Add unfamiliar licences to `kdicts.licensing` with an explicit `outbound` set.
Do not let one default to something permissive.

## Priorities

Where a free wordnet exists, the merge gives roughly an order of magnitude more
coverage than Wiktionary alone, and cross-language pairs come free. Where one
does not, there is no pivot to run and the pair is Wiktionary-only: it has no
sense structure beyond what the translation tables carry, and it is worth
building anyway only where those tables are wide.

Two languages in this repository are in that position. **German and Russian are
both absent from OMW 1.4** — German has OdeNet, which uses interlingual index
ids rather than Princeton offsets and so cannot be pivoted without a mapping
step, and Russian has no open wordnet at all. Both are also among the
best-covered targets in the English edition's translation tables, which is why
`en-de` and `en-ru` are built from Wiktionary alone. `ru-en` is the same
decision in reverse, reading the Russian section of the English edition.
