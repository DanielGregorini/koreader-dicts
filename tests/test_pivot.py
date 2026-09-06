"""The synset pivot: A->B from two wordnets and no bilingual resource."""

from __future__ import annotations

from kdicts.ir import Pos
from kdicts.merge.enrich import attach_inflections, enrich
from kdicts.merge.pivot import PivotConfig, build_pivot, synset_to_lemmas
from kdicts.sources.base import LemmaRecord, SourceSpec, SynsetRecord


class FakeSource:
    """A minimal wordnet, so the pivot can be tested without 60 MB of XML."""

    def __init__(self, source_id, lang, license_id, lemmas, synsets=()):
        self.spec = SourceSpec(id=source_id, kind="fake", path="", lang=lang, license_id=license_id)
        self._lang = lang
        self._license = license_id
        self._lemmas = lemmas
        self._synsets = synsets

    @property
    def lang(self):
        return self._lang

    @property
    def license_id(self):
        return self._license

    def lemmas(self):
        for lemma, synset, rank in self._lemmas:
            yield LemmaRecord(lemma=lemma, synset=synset, rank=rank)

    def synsets(self):
        for synset, pos, gloss, examples in self._synsets:
            yield SynsetRecord(synset=synset, pos=pos, gloss=gloss, examples=examples)


DOG = "02084071-n"
CHASE = "02001858-v"
LONELY = "00003553-a"

ENGLISH = FakeSource(
    "pwn30", "en", "WordNet-3.0",
    [("dog", DOG, 1), ("domestic dog", DOG, 1), ("chase", CHASE, 1), ("lonely", LONELY, 1),
     ("hermit", "99999999-n", 1)],
    [(DOG, Pos.NOUN, "a member of the genus Canis", ("the dog barked",)),
     (CHASE, Pos.VERB, "go after with intent to catch", ()),
     (LONELY, Pos.ADJ, "marked by dejection from being alone", ()),
     ("99999999-n", Pos.NOUN, "one who lives in solitude", ())],
)
PORTUGUESE = FakeSource(
    "omw-pt", "pt", "CC-BY-SA-4.0",
    [("cão", DOG, 1), ("cachorro", DOG, 2), ("perseguir", CHASE, 1), ("solitário", LONELY, 1)],
)
SPANISH = FakeSource(
    "omw-es", "es", "CC-BY-3.0",
    [("perro", DOG, 1), ("perseguir", CHASE, 1), ("solitario", LONELY, 1)],
)


def test_pivot_produces_translations_without_a_bilingual_source():
    dictionary, stats = build_pivot(ENGLISH, PORTUGUESE, gloss_providers=[("en", ENGLISH)])
    assert dictionary.pair == "en-pt"
    assert dictionary.entries["dog"].senses[0].translations == ("cão", "cachorro")
    assert dictionary.entries["chase"].senses[0].translations == ("perseguir",)
    assert stats.shared_synsets == 3


def test_a_third_language_needs_only_a_second_wordnet():
    """The point of the pivot: en->es reuses the same call and no new data."""
    dictionary, _ = build_pivot(ENGLISH, SPANISH, gloss_providers=[("en", ENGLISH)])
    assert dictionary.entries["dog"].senses[0].translations == ("perro",)


def test_pair_with_no_english_on_either_side():
    """es->pt, for which no direct resource exists anywhere in the inputs."""
    dictionary, stats = build_pivot(SPANISH, PORTUGUESE, gloss_providers=[("en", ENGLISH)])
    assert dictionary.pair == "es-pt"
    assert dictionary.entries["perro"].senses[0].translations == ("cão", "cachorro")
    assert dictionary.entries["solitario"].senses[0].translations == ("solitário",)
    assert stats.entries == 3


def test_reverse_direction_is_the_same_call_swapped():
    dictionary, _ = build_pivot(PORTUGUESE, ENGLISH, gloss_providers=[("en", ENGLISH)])
    assert dictionary.pair == "pt-en"
    assert set(dictionary.entries["cão"].senses[0].translations) == {"dog", "domestic dog"}


def test_gloss_only_senses_are_kept_but_counted_separately():
    dictionary, stats = build_pivot(
        ENGLISH, PORTUGUESE, gloss_providers=[("en", ENGLISH)],
        config=PivotConfig(keep_gloss_only=True),
    )
    hermit = dictionary.entries["hermit"]
    assert hermit.senses[0].translations == ()
    assert hermit.senses[0].gloss
    assert stats.senses_gloss_only == 1
    # dog, domestic dog, chase, lonely -- 'dog' and 'domestic dog' are separate
    # source lemmas sharing one synset.
    assert stats.senses_with_translation == 4


def test_gloss_only_senses_can_be_dropped():
    dictionary, stats = build_pivot(
        ENGLISH, PORTUGUESE, gloss_providers=[("en", ENGLISH)],
        config=PivotConfig(keep_gloss_only=False),
    )
    assert "hermit" not in dictionary.entries
    assert stats.senses_dropped_empty == 1


def test_provenance_records_every_contributing_licence():
    dictionary, _ = build_pivot(ENGLISH, PORTUGUESE, gloss_providers=[("en", ENGLISH)])
    assert dictionary.license_ids == frozenset({"WordNet-3.0", "CC-BY-SA-4.0"})
    # A gloss-only sense never touched the target wordnet, so it must not claim
    # that licence -- otherwise dropping the target would drop entries it never
    # contributed to.
    assert dictionary.entries["hermit"].license_ids == frozenset({"WordNet-3.0"})


def test_target_language_gloss_wins_over_the_source_language_one():
    portuguese_glosses = FakeSource(
        "omw-pt", "pt", "CC-BY-SA-4.0",
        [("cão", DOG, 1)],
        [(DOG, Pos.NOUN, "mamífero da família dos canídeos", ())],
    )
    dictionary, _ = build_pivot(
        ENGLISH, portuguese_glosses,
        gloss_providers=[("en", ENGLISH), ("pt", portuguese_glosses)],
        config=PivotConfig(gloss_langs=("pt", "en")),
    )
    sense = dictionary.entries["dog"].senses[0]
    assert sense.gloss == "mamífero da família dos canídeos"
    assert sense.gloss_lang == "pt"


def test_translations_are_capped():
    dictionary, _ = build_pivot(
        ENGLISH, PORTUGUESE, config=PivotConfig(max_translations=1)
    )
    assert dictionary.entries["dog"].senses[0].translations == ("cão",)


def test_synset_to_lemmas_groups_and_deduplicates():
    grouped = synset_to_lemmas(PORTUGUESE)
    assert grouped[DOG] == ["cão", "cachorro"]


def test_enrichment_unions_translations_and_accumulates_licences():
    from kdicts.ir import Entry, Provenance, Sense

    dictionary, _ = build_pivot(ENGLISH, PORTUGUESE, gloss_providers=[("en", ENGLISH)])
    wiktionary = Provenance("wikt-pt", "CC-BY-SA-4.0")
    stats = enrich(dictionary, [
        Entry("dog", "en", [Sense(Pos.NOUN, DOG, ("vira-lata",), provenance=(wiktionary,))]),
        Entry("gizmo", "en", [Sense(Pos.NOUN, None, ("engenhoca",), provenance=(wiktionary,))]),
    ])
    assert stats.entries_added == 1
    assert stats.entries_extended == 1
    dog = dictionary.entries["dog"].senses[0]
    # Union, not replacement: the pivot's translations survive.
    assert dog.translations == ("cão", "cachorro", "vira-lata")
    assert {p.source_id for p in dog.provenance} >= {"omw-pt", "pwn30", "wikt-pt"}


def test_enrichment_can_be_limited_to_existing_headwords():
    from kdicts.ir import Entry, Provenance, Sense

    dictionary, _ = build_pivot(ENGLISH, PORTUGUESE)
    stats = enrich(
        dictionary,
        [Entry("gizmo", "en", [Sense(Pos.NOUN, None, ("engenhoca",),
                                     provenance=(Provenance("w", "CC-BY-SA-4.0"),))])],
        add_new_headwords=False,
    )
    assert stats.entries_added == 0
    assert "gizmo" not in dictionary.entries


def test_attach_inflections_drops_forms_with_no_headword():
    dictionary, _ = build_pivot(ENGLISH, PORTUGUESE)
    added = attach_inflections(dictionary, [("dogs", "dog"), ("wombats", "wombat"), ("dog", "dog")])
    assert added == 1
    assert dictionary.entries["dog"].forms == {"dogs"}
