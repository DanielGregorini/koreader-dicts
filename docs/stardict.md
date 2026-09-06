# StarDict, and the parts that bite

KOReader reads StarDict via sdcv. A dictionary lives at
`koreader/data/dict/<name>/` and consists of:

| file | contents |
|---|---|
| `<name>.ifo` | plain-text metadata, fixed magic first line |
| `<name>.idx` | `word\0` + `uint32be` offset + `uint32be` size, once per headword |
| `<name>.dict` or `.dict.dz` | definition bodies, addressed by those offsets |
| `<name>.syn` | `form\0` + `uint32be` index into the `.idx` |

## The index order is part of the format

`.idx` is looked up by **binary search**, so its order is not a stylistic
choice. Get it wrong and lookups fail *silently* for a fraction of headwords:
the reader reports "not found" for a word that is physically in the file.

The order is StarDict's `stardict_strcmp`: `g_ascii_strcasecmp`, with `strcmp`
as the tiebreak. Two properties are easy to get wrong:

- **`TOLOWER` is ASCII only.** glib deliberately does not touch bytes ≥ 0x80,
  so `Ä` and `ä` are not equal and UTF-8 sequences compare as raw bytes. Any
  use of `str.lower()`, `locale.strxfrm` or `unicodedata.normalize` here is a
  bug.
- **Comparison is on unsigned bytes.** `(guchar)` casts before promotion, so
  `0xC3` sorts *after* `z`, not before it. This is the classic signed-char bug.

`kdicts.collation` implements this as a tuple sort key — `(ascii_folded, raw)` —
and `tests/test_collation.py` proves the key agrees with a comparator
transcribed line by line from the C, over both a hand-built nasty-input set and
random words.

The `.syn` file is binary-searched the same way and needs the same order.

## Other things that bite

**`.ifo` values are single-line.** The parser splits on the first `=` of each
line, so an embedded newline silently truncates everything after it — which for
`description` means losing the attribution. StarDict's own documentation says to
use `<br>`; the writer flattens newlines to that.

**Offsets are 32-bit** in version 2.4.2. Version 3.0.0 adds
`idxoffsetbits=64`, but reader support is patchy, so the writer refuses to
build anything whose body exceeds 4 GiB rather than emitting a file some devices
cannot read.

**No NUL bytes in definitions.** With `sametypesequence` set, the body length
comes from the `.idx`, so a NUL is legal in principle — but readers that hand
the buffer to C string routines truncate at it. The writer rejects them.

**Headwords must be under 256 bytes** and are whitespace-normalised.

**`sametypesequence=h`** means every body is HTML. KOReader renders it with
crengine, which supports a small subset: `b`, `i`, `span`, `div`, `br`, inline
`style` colours. Tables and external CSS either render wrong or render as
literal text in the lookup popup.

## dictzip

`.dict.dz` is an ordinary gzip file — `gunzip` reads it — whose FEXTRA header
carries an `RA` subfield listing the compressed length of every fixed-size chunk
of the original. A reader wanting bytes at offset *o* inflates only the chunk
containing *o*, which is what makes a 50 MB dictionary usable on an e-reader.

The implementation detail that matters: one deflate stream spans the whole file,
with `Z_FULL_FLUSH` after each chunk to reset the LZ77 window so chunks are
independently inflatable, and a final `Z_FINISH` appended *after* the last chunk
and not counted in any chunk length. Compressing each chunk as its own complete
stream produces a file `gunzip` rejects.

## Why not PyGlossary

PyGlossary is the right tool for format conversion and is used as a library for
everything else. Its StarDict writer has a documented history of producing files
KOReader cannot read ([koreader#9455](https://github.com/koreader/koreader/issues/9455)),
and because the failure is silent rather than a crash, a bad file looks like a
working dictionary that just does not know some words. That is worse than a
build failure, so this one piece is ours and is tested accordingly.
