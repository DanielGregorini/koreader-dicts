# tests/

pytest suite for the toolchain. Run it with `pytest -q` from the repository
root.

Everything runs against miniature fixtures built in `fixtures.py` — a handful
of synsets, a few Wiktionary entries, a four-line exception file. No test
downloads anything, so the suite runs offline in under a second.

| file | what it covers |
|---|---|
| `test_stardict_writer.py` | The writer, and the byte layout of the files it produces. |
| `test_collation.py` | The index sort order, against StarDict's own comparator. |
| `test_pivot.py` | Joining two wordnets through shared synset ids. |
| `test_pipeline.py` | A whole build end to end, then read back and binary-searched. |
| `test_licensing.py` | Which combinations of source licences may be bundled, and which must fail. |
| `test_sources.py` | The source adapters, one per input format. |
| `test_render_and_metrics.py` | Entry rendering and the published numbers. |
| `test_cli.py` | The `kdicts` commands. |

The writer and the collation are the pieces whose failure mode is silent: a
wrong sort order produces a dictionary that installs and then reports "not
found" for words that are in the file. Those tests run on every push.
