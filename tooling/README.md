# tooling/

The Python that builds the dictionaries. Installs as the `kdicts` command:

```bash
pip install -e .
```

```
kdicts sources                    what is declared, and what is on disk
kdicts fetch <id>...              download and unpack source data
kdicts build <pair>...            generate dictionaries
kdicts verify <directory>         binary-search a built dictionary
kdicts lookup <directory> <word>  look a word up, the way a device would
kdicts catalog                    write the JSON the website reads
```

## Layout

```
kdicts/
  cli.py         Command line entry point
  config.py      Reads configs/*.toml
  fetch.py       Downloads and verifies source data
  ir.py          The internal representation everything normalises into
  pipeline.py    Runs one build end to end; the order of steps lives here
  licensing.py   Which source licences may be combined, and into what
  collation.py   StarDict's index sort order
  package.py     LICENSE, ATTRIBUTION, README.txt and the .zip
  sources/       One adapter per input format (WordNet, OMW, Wiktionary)
  merge/         The pivot, enrichment, and inflected forms
  writers/       StarDict output: index, dictzip, entry rendering
  verify/        An independent StarDict reader, used to check the output
  bench/         Coverage and the other published metrics
```

`verify/` deliberately shares no code with `writers/`. A check that reused the
writer's own sort key would agree with the writer even when the writer is
wrong.

`docs/build-process.md` explains what each step does.
