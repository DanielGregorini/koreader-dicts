"""Princeton WordNet 3.0, read straight from the WNdb-3.0 ``dict/`` directory.

PWN is the spine of the whole project: it supplies the synset ids every other
wordnet keys against, and the English glosses and examples that make a
gloss-only entry still useful when no translation exists.

Licence: the WordNet 3.0 licence is permissive (BSD-like), explicitly allows
commercial use, and is **not** copyleft.  Its two real obligations are that the
copyright notice survives onto modified copies, and that "Princeton" is not
used in advertising.  Both are handled in :mod:`kdicts.licensing`.

``data.<pos>`` line format::

    synset_offset lex_filenum ss_type w_cnt word lex_id [word lex_id...]
        p_cnt [ptr...] [frames...] | gloss

``w_cnt`` is two hex digits.  Words use ``_`` for spaces and may carry an
adjective syntactic marker in parentheses (``(a)``, ``(p)``, ``(ip)``) that is
not part of the lemma.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

from ..ir import Pos, canonical_synset
from .base import LemmaRecord, SourceError, SourceSpec, SynsetRecord, require_existing

__all__ = ["POS_FILES", "WordNetSource", "parse_gloss"]

#: The suffix of each ``data.``/``index.`` pair, and the synset id tag it uses.
POS_FILES: dict[str, str] = {"noun": "n", "verb": "v", "adj": "a", "adv": "r"}

_MARKER = re.compile(r"\((?:a|p|ip)\)$")

#: The digit after ``%`` in a WordNet sense key names the syntactic category.
_SENSE_KEY_POS = {"1": "n", "2": "v", "3": "a", "4": "r", "5": "s"}


def parse_gloss(raw: str) -> tuple[str, tuple[str, ...]]:
    """Split a WordNet gloss into its definition and its quoted examples.

    A gloss looks like::

        a member of the genus Canis; "the dog barked all night"; "a good dog"

    Semicolon-separated segments that are wholly wrapped in double quotes are
    examples; everything else is definition text.  Some glosses put a citation
    after the quote, which stays with the example.
    """
    definition_parts: list[str] = []
    examples: list[str] = []
    for segment in raw.split(";"):
        segment = segment.strip()
        if not segment:
            continue
        if segment.startswith('"'):
            examples.append(segment.strip('"').strip())
        elif examples:
            # Once examples have started, a trailing unquoted fragment is the
            # continuation of the previous example (a citation), not definition.
            examples[-1] = f"{examples[-1]}; {segment}"
        else:
            definition_parts.append(segment)
    return "; ".join(definition_parts), tuple(e for e in examples if e)


class WordNetSource:
    """Reader for a WNdb-3.0 ``dict/`` directory."""

    def __init__(self, spec: SourceSpec, root: Path) -> None:
        self.spec = spec
        self.root = Path(root)
        self._sense_counts: dict[tuple[str, str], int] | None = None
        require_existing(self.root, spec)
        missing = [p for p in POS_FILES if not (self.root / f"data.{p}").exists()]
        if missing:
            raise SourceError(
                f"source {spec.id!r}: {self.root} does not look like a WNdb dict/ "
                f"directory (missing data.{{{','.join(missing)}}})"
            )

    @property
    def lang(self) -> str:
        return "en"

    @property
    def license_id(self) -> str:
        return self.spec.license_id or "WordNet-3.0"

    # -- reading -------------------------------------------------------------

    def _iter_data_lines(self) -> Iterator[tuple[str, str, str]]:
        """Yield ``(pos_name, tag_from_file, line)`` for real data lines."""
        for pos_name, tag in POS_FILES.items():
            with (self.root / f"data.{pos_name}").open("r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    # The first 29 lines of every data file are a licence header
                    # that begins with two spaces.
                    if line.startswith("  ") or not line.strip():
                        continue
                    yield pos_name, tag, line.rstrip("\n")

    def synsets(self) -> Iterator[SynsetRecord]:
        for _pos_name, _tag, line in self._iter_data_lines():
            head, _, gloss_text = line.partition("|")
            fields = head.split()
            offset, _lex_filenum, ss_type = fields[0], fields[1], fields[2]
            definition, examples = parse_gloss(gloss_text.strip())
            yield SynsetRecord(
                synset=canonical_synset(offset, ss_type),
                pos=Pos.from_wordnet_tag(ss_type),
                gloss=definition,
                examples=examples,
            )

    def sense_counts(self) -> dict[tuple[str, str], int]:
        """``(lemma, synset) -> corpus tag count``, from ``index.sense``.

        Each line is ``sense_key synset_offset sense_number tag_cnt``, where
        the tag count is how many times that exact sense was annotated in
        WordNet's sense-tagged corpora.  It is the only frequency evidence in
        the distribution that is comparable *across* parts of speech:
        ``behind%4:02:00::`` (adverb) is tagged 13 times, ``behind%1:08:00::``
        (the noun) once.  Without it, ordering has to fall back on a fixed
        noun-first convention that is wrong for a large minority of entries.

        Cached, because the file has ~207k lines and every entry consults it.
        """
        if self._sense_counts is None:
            counts: dict[tuple[str, str], int] = {}
            path = self.root / "index.sense"
            if path.exists():
                with path.open("r", encoding="utf-8", errors="replace") as handle:
                    for line in handle:
                        fields = line.split()
                        if len(fields) < 4:
                            continue
                        key, offset, _number, tag_count = fields[0], fields[1], fields[2], fields[3]
                        lemma, _, rest = key.partition("%")
                        tag = _SENSE_KEY_POS.get(rest[:1])
                        if not tag:
                            continue
                        entry = (lemma.replace("_", " "), canonical_synset(offset, tag))
                        # A satellite and its head can collapse onto one
                        # canonical id; keep the larger count.
                        previous = counts.get(entry, 0)
                        counts[entry] = max(previous, int(tag_count))
            self._sense_counts = counts
        return self._sense_counts

    def lemmas(self) -> Iterator[LemmaRecord]:
        """Lemma -> synset mappings, ranked by WordNet's own sense order.

        The rank comes from ``index.<pos>``, whose synset offsets are listed in
        sense-number order (most frequent first).  Keeping that order is what
        puts "a domesticated carnivore" above "a hot dog" on the *dog* entry.
        """
        counts = self.sense_counts()
        for pos_name, tag in POS_FILES.items():
            index_path = self.root / f"index.{pos_name}"
            if not index_path.exists():
                continue
            with index_path.open("r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    if line.startswith("  ") or not line.strip():
                        continue
                    fields = line.split()
                    lemma = fields[0].replace("_", " ")
                    pointer_count = int(fields[3])
                    cursor = 4 + pointer_count
                    synset_count = int(fields[cursor])
                    cursor += 2  # skip sense_cnt (repeat) and tagsense_cnt
                    offsets = fields[cursor : cursor + synset_count]
                    for rank, offset in enumerate(offsets, start=1):
                        # index.adj lists head adjectives and satellites
                        # together; canonical_synset folds both onto "-a", which
                        # is also what index.<pos> implies for the other three.
                        synset = canonical_synset(offset, tag)
                        yield LemmaRecord(
                            lemma=lemma,
                            synset=synset,
                            rank=rank,
                            frequency=counts.get((lemma, synset), 0),
                        )

    def synset_members(self) -> Iterator[tuple[str, str]]:
        """``(synset_id, lemma)`` pairs taken from the data files.

        ``index.<pos>`` gives ranked lemma->synset; this gives the reverse, and
        is what the pivot uses when English is the *target* side.
        """
        for _pos_name, _tag, line in self._iter_data_lines():
            head, _, _ = line.partition("|")
            fields = head.split()
            offset, ss_type = fields[0], fields[2]
            word_count = int(fields[3], 16)
            synset = canonical_synset(offset, ss_type)
            for index in range(word_count):
                word = fields[4 + index * 2]
                yield synset, _MARKER.sub("", word).replace("_", " ")
