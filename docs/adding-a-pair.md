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
kdicts fetch omw-it
kdicts build en-it
```

The CI matrix picks up new pairs automatically; nothing in the workflow needs
editing.

### Reverse direction

Swap `source_side` and `target_side`. That is the whole change.

### A pair with no English on either side

Also just config — `configs/pairs/es-pt.toml` is the worked example. Neither
side needs to know the other exists; they meet at the synset ids.

Note what you lose: inflected forms. The rule-based inflector is English-only,
and non-English Wiktionary form tables are not wired in yet, so `es-pt` ships
with an empty `.syn`. That is visible in the metrics, and it is the honest state
of the pair rather than something to paper over.

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
does not — Russian, Turkish, Korean, Hindi, Vietnamese, Ukrainian, Hungarian —
there is no advantage and the result would be a worse clone of the incumbent.
Those pairs are last, and Wiktionary-only.

Note also that **German is absent from OMW 1.4 entirely**; `en-de` needs OdeNet
added as its own source before it can be built.
