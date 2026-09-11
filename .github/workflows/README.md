# workflows/

`pages.yml` builds the website and publishes it to GitHub Pages on every push
to `main`. It runs Node only.

`build-dictionaries.yml` rebuilds the dictionaries on the first of every month,
and on demand, one runner per pair. It leaves out the pairs that read the
500 MB English Wiktionary dump, which are built by hand. Nothing it produces is
published: each archive is uploaded as a workflow artifact, so a rebuild
against changed upstream data can be looked at before it replaces what people
download.
