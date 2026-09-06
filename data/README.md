# data/

Downloaded source data. Nothing here is committed except this file.

`kdicts fetch` populates it from the URLs in `configs/sources.toml`, verifying
each download against its checksum and unpacking archives to the paths the
adapters expect. Downloads are cached under `data/.cache/`, so re-running fetch
does not re-download anything already present.

It gets large — the English Wiktionary dump alone is around 500 MB. Delete the
whole directory whenever you want; the next fetch rebuilds it.
