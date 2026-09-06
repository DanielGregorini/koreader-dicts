# dictionaries/

Build output. `kdicts build` writes one directory per pair here:

```
dictionaries/en-pt/
  en-pt/            the dictionary itself: .ifo .idx .dict.dz .syn
                    plus LICENSE, ATTRIBUTION and README.txt
  en-pt.zip         the same folder, zipped for download
  metrics.json      entry counts, coverage, sources and licences
```

None of it is committed. The archives are published to GitHub Releases, which
is where the website links.

The one exception is `catalog.json`, written by `kdicts catalog`. It collects
every `metrics.json` into a single small file, and the website reads it at
build time to render the dictionary list and the per-dictionary pages. It is
committed so the site can build without running the Python toolchain — after a
rebuild, run `kdicts catalog` and commit the result.
