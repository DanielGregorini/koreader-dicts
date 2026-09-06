"""Rendering and the published metrics."""

from __future__ import annotations

from kdicts.bench.metrics import load_frequency_list, measure
from kdicts.ir import Dictionary, Entry, Pos, Provenance, Sense
from kdicts.writers.render import RenderOptions, render_entry

WORDNET = Provenance("pwn30", "WordNet-3.0")
WIKT = Provenance("wikt-pt", "CC-BY-SA-4.0")


def entry(**kwargs) -> Entry:
    base = {"headword": "dog", "lang": "en", "senses": [], "forms": set()}
    base.update(kwargs)
    return Entry(**base)


# --- rendering ---------------------------------------------------------------


def test_renders_translations_before_the_gloss():
    html = render_entry(entry(senses=[
        Sense(Pos.NOUN, "1-n", ("cão", "cachorro"), "a member of the genus Canis",
              "en", provenance=(WORDNET,))
    ]), RenderOptions(target_lang="pt"))
    assert html.index("cão") < html.index("a member of the genus")
    assert "<b>cão, cachorro</b>" in html


def test_gloss_only_sense_is_not_muted_into_illegibility():
    html = render_entry(entry(senses=[
        Sense(Pos.NOUN, "1-n", (), "a dull unattractive girl", "en", provenance=(WORDNET,))
    ]))
    assert "<span>a dull unattractive girl</span>" in html


def test_gloss_that_restates_the_translation_is_dropped():
    """"**cão** -- cão" is how a merged dictionary looks sloppy."""
    html = render_entry(entry(senses=[
        Sense(Pos.NOUN, None, ("cão",), "cão", "pt", provenance=(WIKT,))
    ]))
    assert html.count("cão") == 1
    assert "&mdash;" not in html


def test_sense_adding_nothing_new_is_dropped():
    html = render_entry(entry(senses=[
        Sense(Pos.NOUN, "1-n", ("cão",), "a member of the genus Canis", "en",
              provenance=(WORDNET,), rank=1),
        Sense(Pos.NOUN, None, ("cão",), "", "", provenance=(WIKT,), rank=50),
        Sense(Pos.NOUN, None, ("vira-lata",), "", "", provenance=(WIKT,), rank=51),
    ]))
    assert "vira-lata" in html
    assert html.count("cão") == 1


def test_parts_of_speech_are_grouped_and_ordered():
    html = render_entry(entry(senses=[
        Sense(Pos.VERB, "2-v", ("perseguir",), provenance=(WORDNET,)),
        Sense(Pos.NOUN, "1-n", ("cão",), provenance=(WORDNET,)),
    ]))
    assert html.index("<i>n.</i>") < html.index("<i>v.</i>")


def test_senses_are_capped():
    senses = [Sense(Pos.NOUN, f"{i}-n", (f"t{i}",), provenance=(WORDNET,), rank=i)
              for i in range(20)]
    html = render_entry(entry(senses=senses), RenderOptions(max_senses_per_pos=3))
    assert "t2" in html and "t3" not in html


def test_html_is_escaped():
    html = render_entry(entry(senses=[
        Sense(Pos.NOUN, "1-n", ("<script>",), 'a & b "c"', "en", provenance=(WORDNET,))
    ]))
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "a &amp; b" in html


def test_rtl_target_gets_a_direction_wrapper():
    senses = [Sense(Pos.NOUN, "1-n", ("كلب",), provenance=(WORDNET,))]
    assert render_entry(entry(senses=senses), RenderOptions(target_lang="ar")).startswith(
        '<div dir="rtl">'
    )
    assert not render_entry(entry(senses=senses), RenderOptions(target_lang="pt")).startswith(
        '<div dir="rtl">'
    )


def test_entry_with_nothing_to_say_renders_empty():
    assert render_entry(entry(senses=[Sense(Pos.NOUN, "1-n", (), "", "")])) == ""


# --- metrics -----------------------------------------------------------------


def build_dictionary() -> Dictionary:
    dictionary = Dictionary("en", "pt")
    dictionary.add(entry(
        headword="dog",
        senses=[Sense(Pos.NOUN, "1-n", ("cão",), "a member of the genus Canis", "en",
                      ("the dog barked",), provenance=(WORDNET,))],
        forms={"dogs"},
        pronunciations=("/dɔɡ/",),
    ))
    dictionary.add(entry(
        headword="hermit",
        senses=[Sense(Pos.NOUN, "2-n", (), "one who lives in solitude", "en",
                      provenance=(WORDNET,))],
        forms={"hermits"},
    ))
    dictionary.add(entry(
        headword="gizmo",
        senses=[Sense(Pos.NOUN, None, ("engenhoca",), provenance=(WIKT,))],
    ))
    return dictionary


def test_gloss_only_entries_are_never_counted_as_translations():
    metrics = measure(build_dictionary())
    assert metrics.entries == 3
    assert metrics.entries_with_translation == 2
    assert metrics.entries_gloss_only == 1
    assert metrics.senses_with_translation == 2
    assert metrics.senses_gloss_only == 1
    assert metrics.percent_entries_with_translation == 66.67


def test_coverage_counts_inflected_forms_separately_from_headwords():
    """The number that predicts whether a lookup on a real page succeeds."""
    metrics = measure(
        build_dictionary(),
        frequency_words=["dog", "dogs", "hermit", "absent"],
        cutoffs=[4],
    )
    point = metrics.coverage[0]
    assert point["sampled"] == 4
    assert point["headword_hits"] == 2   # dog, hermit
    assert point["form_hits"] == 1       # dogs, via the .syn index
    assert point["percent"] == 75.0


def test_other_published_figures():
    metrics = measure(build_dictionary())
    assert metrics.inflected_forms == 2
    assert metrics.entries_with_example == 1
    assert metrics.entries_with_pronunciation == 1
    assert metrics.entries_with_forms == 2
    assert metrics.mean_definition_chars > 0
    assert metrics.mean_translations_per_entry == round(2 / 3, 2)
    assert sorted(metrics.licenses) == ["CC-BY-SA-4.0", "WordNet-3.0"]


def test_metrics_serialise_with_the_derived_percentages():
    data = measure(build_dictionary()).to_dict()
    assert data["percent_entries_with_translation"] == 66.67
    assert data["percent_entries_with_forms"] == round(100 * 2 / 3, 2)


def test_frequency_list_accepts_word_and_word_count_lines(tmp_path):
    path = tmp_path / "freq.txt"
    path.write_text("you 28787591\ni 27086011\nthe\nYOU 5\n", encoding="utf-8")
    assert load_frequency_list(path) == ["you", "i", "the"]
    assert load_frequency_list(path, limit=2) == ["you", "i"]
