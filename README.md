# koreader-dicts

Dictionaries for [KOReader](https://koreader.rocks/), built from public sources.

Look a word up while reading and get a real definition, not a blank popup.
Inflected forms are indexed, so tapping *wielded* finds *wield*, and tapping
*geese* finds *goose*.

**[Browse all dictionaries →](https://danielgregorini.github.io/koreader-dicts/)**

Not affiliated with the KOReader project.

## Download

Click a name to download. No account, no installer, nothing to sign up for.

| dictionary | languages | entries | inflected forms | size | licence |
|---|---|---:|---:|---:|---|
| **[en-pt](https://github.com/DanielGregorini/koreader-dicts/releases/latest/download/en-pt.zip)** | English → Portuguese | 172,838 | 395,314 | 15 MB | CC BY-SA 4.0 |
| **[en-es](https://github.com/DanielGregorini/koreader-dicts/releases/latest/download/en-es.zip)** | English → Spanish | 174,258 | 396,782 | 15 MB | CC BY-SA 4.0 |
| **[en-fr](https://github.com/DanielGregorini/koreader-dicts/releases/latest/download/en-fr.zip)** | English → French | 84,803 | 127,148 | 7 MB | CeCILL-C |
| **[pt-en](https://github.com/DanielGregorini/koreader-dicts/releases/latest/download/pt-en.zip)** | Portuguese → English | 54,042 | — | 4 MB | CC BY-SA 4.0 |
| **[es-pt](https://github.com/DanielGregorini/koreader-dicts/releases/latest/download/es-pt.zip)** | Spanish → Portuguese | 20,263 | — | 2 MB | CC BY-SA 4.0 |

Full measurements for each one — including how much of a real page of prose it
can resolve — are on the [site](https://danielgregorini.github.io/koreader-dicts/).

## Install

Unzip the download and copy the **folder** — not its contents — into the
dictionary directory for your device:

| device | directory |
|---|---|
| Kindle | `koreader/data/dict` |
| Kobo | `.adds/koreader/data/dict/` |
| Android | `/sdcard/koreader/data/dict` |
| PocketBook | `applications/koreader/data/dict` |
| Cervantes | `/mnt/private/koreader/data/dict` |
| Linux | `$HOME/.config/koreader/data/dict` |
| macOS | `$HOME/Library/Application Support/koreader/data/dict` |

You should end up with `koreader/data/dict/en-pt/en-pt.ifo`.

Restart KOReader. The dictionary appears in the lookup popup. Long-press a
dictionary name there to reorder them when you have several installed.

## How they are made

A wordnet groups words by meaning rather than by spelling, and every wordnet in
the Open Multilingual Wordnet reuses the same identifying numbers for those
groups. So the same concept carries the same number in every language:

```
"wield"  →  01095899-v  →  "empunhar", "manejar"
```

Joining on that number produces a bilingual dictionary without any
English-Portuguese resource being consulted. Wiktionary is then merged on top
for the slang, idiom and inflected forms that wordnets do not carry.

`docs/build-process.md` walks through the whole thing, step by step.

## Building it yourself

```bash
pip install -e .
kdicts fetch pwn30 omw-pt wikt-pt wikt-en-pt
kdicts build en-pt --verify-sample 5000
kdicts catalog
```

Adding a language pair is a config file and no code — see
`docs/adding-a-pair.md`.

## Sources

| source | credit | licence |
|---|---|---|
| Princeton WordNet 3.0 | Princeton University | WordNet-3.0 |
| OpenWN-PT | de Paiva & Rademaker, via Open Multilingual Wordnet 1.4 | CC BY-SA 4.0 |
| Multilingual Central Repository | Spanish, via Open Multilingual Wordnet 1.4 | CC BY 3.0 |
| MultiWordNet | Italian, via Open Multilingual Wordnet 1.4 | CC BY 3.0 |
| Japanese Wordnet | via Open Multilingual Wordnet 1.4 | WordNet-3.0 |
| Wordnet Bahasa | Indonesian, via Open Multilingual Wordnet 1.4 | MIT |
| WOLF | French, via Open Multilingual Wordnet 1.4 | CeCILL-C |
| Wiktionary | via [kaikki.org](https://kaikki.org/) (wiktextract) | CC BY-SA 4.0 |
| OpenSubtitles 2018 frequency lists | hermitdave/FrequencyWords | CC BY-SA 4.0 |

Every dictionary ships `LICENSE` and `ATTRIBUTION` files naming the sources
that went into it. A dictionary's licence is whatever its sources allow, so it
is not the same across all pairs.

## Licence

The toolchain and the website are MIT — see [LICENSE](LICENSE). The
dictionaries carry the licences listed above.
