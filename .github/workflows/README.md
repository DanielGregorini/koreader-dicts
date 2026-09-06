# workflows/

`pages.yml` builds the website and publishes it to GitHub Pages on every push
to `main`. It runs Node only — the dictionaries are built separately and
uploaded to Releases, so nothing here needs Python.
