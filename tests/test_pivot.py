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


def test_synset_frequencies_order_senses_when_the_source_side_has_none():
    """OMW lexicons carry no tag counts, so without this every non-English
    entry opened with whichever sense the lexicon happened to list first."""
    VULGAR = "05220461-n"
    spanish = FakeSource("omw-es", "es", "CC-BY-3.0", [("patata", VULGAR, 1), ("patata", DOG, 2)])
    portuguese = FakeSource("omw-pt", "pt", "CC-BY-SA-4.0", [("xoxota", VULGAR, 1), ("cão", DOG, 1)])
    dictionary, _ = build_pivot(spanish, portuguese, synset_frequencies={DOG: 40})
    senses = dictionary.entries["patata"].senses_by_pos()[0][1]
    assert [s.translations for s in senses] == [("cão",), ("xoxota",)]
    assert [s.frequency for s in senses] == [40, 0]


def test_a_sense_two_sources_agree_on_outranks_a_more_frequent_synset():
    """The vulgar synset *patata* maps onto is tagged more often in English than
    the potato one, because "vagina" is an ordinary anatomical word there. The
    Spanish Wiktionary does not know the vulgar sense. Agreement wins."""
    from kdicts.ir import Sense

    VULGAR = "05521514-n"
    spanish = FakeSource("omw-es", "es", "CC-BY-3.0", [("patata", VULGAR, 1), ("patata", DOG, 2)])
    portuguese = FakeSource("omw-pt", "pt", "CC-BY-SA-4.0", [("xoxota", VULGAR, 1), ("cão", DOG, 1)])
    dictionary, _ = build_pivot(spanish, portuguese, synset_frequencies={VULGAR: 5, DOG: 2})
    entry = dictionary.entries["patata"]
    assert [s.translations for s in entry.senses_by_pos()[0][1]] == [("xoxota",), ("cão",)]

    wiktionary = Sense(pos=Pos.NOUN, translations=("cão",), gloss="tubérculo", rank=51)
    entry.senses.append(wiktionary)
    ordered = entry.senses_by_pos()[0][1]
    assert [s.translations for s in ordered] == [("cão",), ("cão",), ("xoxota",)]
    assert ordered[0].synset == DOG


def test_wiktionarys_first_sense_leads_when_the_wordnet_lacks_the_main_one():
    """Open Dutch WordNet has no word for the bird, only for the fool, so the
    pivot gives *goose* one translated sense: the fool. Wiktionary's first
    sense, *gans*, is the reader's answer and must not sit below it."""
    from kdicts.ir import Sense

    BIRD, FOOL = "01855672-n", "10157744-n"
    english = FakeSource("pwn30", "en", "WordNet-3.0", [("goose", BIRD, 1), ("goose", FOOL, 2)])
    dutch = FakeSource("omw-nl", "nl", "CC-BY-SA-4.0", [("oliebol", FOOL, 1)])
    dictionary, _ = build_pivot(english, dutch, config=PivotConfig(keep_gloss_only=True))
    entry = dictionary.entries["goose"]
    entry.senses.append(Sense(pos=Pos.NOUN, translations=("gans",), gloss="waterfowl", rank=1))
    ordered = entry.senses_by_pos()[0][1]
    assert [s.translations for s in ordered][:2] == [("gans",), ("oliebol",)]


def test_wordnets_own_zero_count_is_not_replaced_by_the_synset_total():
    """WordNet says *goose* was never tagged as a fool. That zero is evidence,
    and the synset total -- mostly *jackass* -- must not stand in for it."""
    BIRD, FOOL = "01855672-n", "10157744-n"

    class WordNetLike(FakeSource):
        def sense_counts(self):
            return {}

    english = WordNetLike("pwn30", "en", "WordNet-3.0", [("goose", BIRD, 1), ("goose", FOOL, 2)])
    dutch = FakeSource("omw-nl", "nl", "CC-BY-SA-4.0", [("gans", BIRD, 1), ("oliebol", FOOL, 1)])
    dictionary, _ = build_pivot(english, dutch, synset_frequencies={FOOL: 40})
    assert all(sense.frequency == 0 for sense in dictionary.entries["goose"].senses)


def test_a_vocalized_lemma_is_not_listed_as_its_own_synonym():
    """The Arabic WordNet writes its lemmas with vowels. The headword is made
    bare so a reader can reach it; the synonyms keep their vowels; and the word
    must still recognise itself across that difference."""
    arabic = FakeSource("omw-arb", "ar", "CC-BY-SA-3.0", [("كَلْب", DOG, 1), ("جَرْو", DOG, 2)])
    dictionary, _ = build_pivot(arabic, arabic, config=PivotConfig(keep_gloss_only=False))
    entry = dictionary.entries["كلب"]
    assert entry.senses[0].translations == ("جَرْو",)


def test_english_verbs_agree_across_the_infinitive_marker():
    """Wiktionary says "to go"; WordNet says "go". The Arabic WordNet also maps
    *ذهب* onto *be*, the most-tagged synset in English, and only agreement can
    put *go* above it."""
    from kdicts.ir import Sense

    BE, GO = "02604760-v", "01835496-v"
    arabic = FakeSource("omw-arb", "ar", "CC-BY-SA-3.0", [("ذهب", BE, 1), ("ذهب", GO, 2)])
    english = FakeSource("pwn30", "en", "WordNet-3.0", [("be", BE, 1), ("go", GO, 1), ("travel", GO, 2)])
    dictionary, _ = build_pivot(arabic, english, synset_frequencies={BE: 9000, GO: 300})
    entry = dictionary.entries["ذهب"]
    entry.senses.append(Sense(pos=Pos.VERB, translations=("to go", "to travel"), gloss="to go", rank=1))
    without = [s.translations for s in entry.senses_by_pos()[0][1]]
    assert without[0] == ("be",)
    ordered = [s.translations for s in entry.senses_by_pos("en")[0][1]]
    assert ordered[0] == ("go", "travel")


def test_a_monolingual_entry_leads_with_its_commonest_sense_even_without_synonyms():
    """WordNet's bird synset has one member, so pivoting WordNet against itself
    leaves that sense with a definition and no synonym. It is still the sense a
    reader means, and the fool synset's synonyms must not put the fool first."""
    BIRD, FOOL = "01855672-n", "10157744-n"

    class WordNetLike(FakeSource):
        def sense_counts(self):
            return {}

        def lemmas(self):
            for lemma, synset, rank in self._lemmas:
                tagged = 3 if (lemma, synset) == ("goose", BIRD) else 0
                yield LemmaRecord(lemma=lemma, synset=synset, rank=rank, frequency=tagged)

    english = WordNetLike(
        "pwn30", "en", "WordNet-3.0",
        [("goose", BIRD, 1), ("goose", FOOL, 2), ("jackass", FOOL, 1), ("bozo", FOOL, 2)],
        synsets=[(BIRD, Pos.NOUN, "web-footed waterfowl", ()), (FOOL, Pos.NOUN, "a stupid fool", ())],
    )
    dictionary, _ = build_pivot(
        english, english, gloss_providers=[("en", english)], config=PivotConfig(keep_gloss_only=True)
    )
    goose = dictionary.entries["goose"]
    # Under the bilingual rules the synonym-bearing sense wins ...
    assert next(s.gloss for s in goose.senses_by_pos()[0][1]) == "a stupid fool"
    # ... and under the monolingual ones frequency does.
    assert [s.gloss for s in goose.senses_by_pos("en")[0][1]] == ["web-footed waterfowl", "a stupid fool"]


def test_a_wiktionary_only_monolingual_entry_keeps_the_editions_order():
    from kdicts.ir import Entry, Sense

    entry = Entry(
        headword="batata", lang="pt",
        senses=[
            Sense(pos=Pos.NOUN, gloss="tubérculo da batateira", rank=1),
            Sense(pos=Pos.NOUN, gloss="mentira", translations=("peta",), rank=3),
        ],
    )
    assert [s.gloss for s in entry.senses_by_pos("pt")[0][1]] == ["tubérculo da batateira", "mentira"]


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
