"""Render an :class:`~kdicts.ir.Entry` to the HTML body of a StarDict entry.

KOReader renders dictionary bodies with crengine, which supports a small subset
of HTML.  Anything fancier than the tags used here -- external CSS, tables,
flexbox -- either renders wrong or renders as literal text in the lookup popup,
so the markup stays deliberately plain.

The shape is chosen for a lookup popup two or three lines tall: translations
first and in bold, because that is what the reader wants 90% of the time, then
the definition, then examples.  A reader who taps a word mid-sentence should
get their answer without scrolling.
"""

from __future__ import annotations

from dataclasses import dataclass
from html import escape

from ..ir import Entry, Pos, Sense

__all__ = ["RTL_LANGS", "RenderOptions", "render_entry"]

#: Languages whose target text needs an explicit direction, or it renders
#: mangled next to Latin-script glosses.
RTL_LANGS: frozenset[str] = frozenset({"ar", "he", "fa", "ur", "arb", "heb", "fas", "urd"})


@dataclass(slots=True)
class RenderOptions:
    target_lang: str = ""
    show_gloss: bool = True
    show_examples: bool = True
    show_pronunciation: bool = True
    show_labels: bool = True
    #: Cap senses per part of speech. A wordnet entry for "run" has 41 verb
    #: senses; nobody reads past the first handful in a popup.
    max_senses_per_pos: int = 6
    max_examples_per_sense: int = 2
    #: Colour for secondary text. Grey reads as secondary on e-ink too.
    muted_color: str = "#666666"

    @property
    def rtl(self) -> bool:
        return self.target_lang in RTL_LANGS


def _gloss_adds_nothing(sense: Sense) -> bool:
    """True when the gloss is just the translation restated.

    Wiktionary's foreign-language editions often define an English word with a
    bare equivalent, so the same sense arrives with ``translations=("cao",)``
    and ``gloss="cao"``. Rendered naively that reads ``**cao** -- cao``, which
    is the single most visible way a merged dictionary looks sloppy.
    """
    if not sense.gloss or not sense.translations:
        return False
    gloss = sense.gloss.strip().rstrip(".").lower()
    if gloss in {t.strip().rstrip(".").lower() for t in sense.translations}:
        return True
    return gloss == ", ".join(sense.translations).strip().lower()


def _redundant_senses(senses: list[Sense]) -> set[int]:
    """Indices of senses that say nothing a previous sense has not already said.

    Enrichment can add a translation-only sense whose words all appeared in an
    earlier pivot sense -- true, but not worth a line in a lookup popup.
    """
    seen: set[str] = set()
    redundant: set[int] = set()
    for index, sense in enumerate(senses):
        words = {t.strip().lower() for t in sense.translations}
        informative = sense.gloss and not _gloss_adds_nothing(sense)
        if words and not informative and not sense.examples and words <= seen:
            redundant.add(index)
        else:
            seen |= words
    return redundant


def _sense_html(sense: Sense, index: int, options: RenderOptions) -> str:
    """HTML for one sense, or "" when it has nothing to say.

    Returning a bare "1." for a sense with no translation and no gloss would
    put an empty numbered line in the lookup popup, and the writer would happily
    ship it.
    """
    if not sense.translations and not sense.gloss:
        return ""
    parts: list[str] = [f'<span style="color:{options.muted_color}">{index}.</span> ']

    if options.show_labels and sense.labels:
        labels = ", ".join(escape(label) for label in sense.labels[:3])
        parts.append(f'<i style="color:{options.muted_color}">({labels})</i> ')

    if sense.translations:
        rendered = ", ".join(escape(t) for t in sense.translations)
        parts.append(f"<b>{rendered}</b>")

    if options.show_gloss and sense.gloss and not _gloss_adds_nothing(sense):
        gloss = escape(sense.gloss)
        if sense.translations:
            parts.append(f' <span style="color:{options.muted_color}">&mdash; {gloss}</span>')
        else:
            # Gloss-only: it is all the reader gets, so do not mute it into
            # illegibility on a low-contrast screen.
            parts.append(f"<span>{gloss}</span>")

    if options.show_examples and sense.examples:
        for example in sense.examples[: options.max_examples_per_sense]:
            parts.append(
                f'<br/><i style="color:{options.muted_color}">&ldquo;{escape(example)}&rdquo;</i>'
            )

    return "".join(parts)


def render_entry(entry: Entry, options: RenderOptions | None = None) -> str:
    """HTML body for *entry*, for a ``sametypesequence=h`` dictionary."""
    options = options or RenderOptions()
    blocks: list[str] = []

    if options.show_pronunciation and entry.pronunciations:
        ipa = escape(entry.pronunciations[0])
        blocks.append(f'<div style="color:{options.muted_color}">{ipa}</div>')

    for pos, senses in entry.senses_by_pos():
        label = pos.label
        header = f"<i>{escape(label)}</i> " if label else ""
        skip = _redundant_senses(senses)
        kept = [sense for index, sense in enumerate(senses) if index not in skip]
        rendered = [
            html
            for html in (
                _sense_html(sense, index, options)
                for index, sense in enumerate(kept[: options.max_senses_per_pos], start=1)
            )
            if html
        ]
        if not rendered:
            continue
        body = "<br/>".join(rendered)
        blocks.append(f"<div>{header}{body}</div>")

    if not blocks:
        return ""

    html = "".join(blocks)
    if options.rtl:
        html = f'<div dir="rtl">{html}</div>'
    return html


def entry_is_renderable(entry: Entry) -> bool:
    return any(sense.translations or sense.gloss for sense in entry.senses)


def pos_label(pos: Pos) -> str:
    return pos.label
