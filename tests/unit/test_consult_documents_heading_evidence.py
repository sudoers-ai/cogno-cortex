"""``consult_documents`` — the floor's ONE exception: evidence by the section HEADING.

A passage below the HYBRID floor passes when EVERY content word of its section heading (the leaf
of its ``heading_path``) is in ONE of the texts searched, and that heading has at least
``MIN_HEADING_WORDS`` content words. Over the REAL in-memory store, INVENTED data only: the
documents, the inn, the years and the figures are made up. What is kept from the measured case
is its FORM — a section that is a table (years and values, little prose), a numbered heading of
several words, the right passage FIRST with a fused score under the floor, and a reading that
said *nothing relevant* over it.

The in-memory store's lexical measure is the share of the question's distinct words a passage
carries, and a passage's content starts with its heading path, so the heading's words count
there too; the fused score is ``0.6·v + 0.4·l``. Vectors are the axes of ``documents_support``:
a question is embedded as ``NEUTRAL`` unless a test maps it to another axis, and ``v`` is a
passage's cosine to the question's vector.

The new names are read off the MODULE (``cd.X``), never imported by name, so this file collects
against a tree without them — the twin is run in the broken world too, and fails there on its
first assertion (the outcome), not on an import.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import math

import pytest

import cogno_cortex.skills.consult_documents as cd
from cogno_cortex import ToolContext
from cogno_cortex.skills.consult_documents import (
    CUT_FLOOR,
    CUT_LEXICAL_EVIDENCE,
    META_DOCUMENTS_ACCESS,
    OUTCOME_HITS,
    OUTCOME_NOTHING_RELEVANT,
    ConsultDocumentsTool,
    DocumentsAccess,
)
from tests.unit.documents_support import MODEL_B, KeyedEmbedder, access, axis, publish, store

# The host's numbers on the hybrid scale (a floor of 0.40, an evidence floor of 0.13): the ones
# the measured reading was cut under. Passed explicitly — the skill has no defaults for either.
FLOOR = 0.40
EVIDENCE = 0.13

TITLE = "Relatório anual da Pousada Vento Norte"

# ``v = 0.25`` against NEUTRAL (1 / √(15 + 1)), and ``0`` against every other axis a question uses.
QUARTER = [0.0, 0.0, 0.0, math.sqrt(15.0), 0.0, 0.0, 0.0, 1.0]

TABLE = ("| Ano | Diária média |\n|---|---|\n| 2019 | R$ 210 |\n| 2021 | R$ 185 |\n"
         "| 2023 | R$ 240 |")
LOCATION = ("A pousada fica a 2 km do centro, com acesso por estrada asfaltada.",
            ("3. Localização e Acesso",), None, axis(1))
SERVICES = ("Café da manhã, estacionamento e wi-fi estão incluídos.",
            ("5. Serviços Incluídos",), None, axis(2))
RATES = (TABLE, ("12. Variação das Diárias",), None, QUARTER)

# The contact's words and the model's rewrite — the two texts searched.
ASKED = "Como foi a variação das diárias?"
REWRITE = "variação das diárias ao longo dos anos"


async def inn():
    st = store()
    doc = await publish(st, title=TITLE, chunks=[LOCATION, SERVICES, RATES])
    return st, doc


def kb(doc: str, ordinal: int) -> str:
    return f"kb:{doc}.1.{ordinal}"


async def run(acc: DocumentsAccess, query: str):
    tool = ConsultDocumentsTool(query=query)
    return await tool.run(ToolContext(metadata={META_DOCUMENTS_ACCESS: acc}))


def hybrid(st, **kw) -> DocumentsAccess:
    base = dict(hybrid_floor=FLOOR, lexical_floor=0.3, lexical_evidence_floor=EVIDENCE)
    base.update(kw)
    return access(st, **base)


def legacy_digest(record, result, doc: str) -> str:
    """What the tree before this change would have produced, as one digest: the record WITHOUT
    the new field, the payload and the evidence — the document's id (a fresh ``uuid4`` per run)
    written as ``DOC``. Pinned below from ``main`` (d42aa6c)."""
    fields = {k: v for k, v in dataclasses.asdict(record).items() if k != "heading_match"}
    blob = json.dumps({"record": fields, "payload": result.payload,
                       "evidence": list(result.evidence)}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.replace(doc, "DOC").encode()).hexdigest()


# ── the twin: the FORM of the measured case ───────────────────────────────────────────

async def test_TWIN_a_table_section_under_the_floor_passes_by_its_heading():
    st, doc = await inn()
    acc = hybrid(st, user_text=ASKED)
    res = await run(acc, REWRITE)
    rec = acc.records[0]
    # On main: nothing_relevant, cut_by=floor, below_floor=3 — «I found nothing», over the table.
    assert rec.outcome == OUTCOME_HITS, rec
    assert rec.cut_by is None
    assert rec.hit_ids == (kb(doc, 2),), "the table, and only the table"
    # the FORM: the right passage is the best of all, and under the floor
    assert rec.scores == (0.35,) and rec.scores[0] < FLOOR
    assert rec.below_floor == 3, "all three passages scored under the floor"
    assert rec.heading_match == 1
    # it still faced the evidence gate, and cleared it on its own words
    assert rec.lexical_evidence == 0.5 and rec.lexical_evidence >= EVIDENCE
    assert "heading_match=1" in res.evidence and "below_floor=3" in res.evidence
    assert "| 2021 | R$ 185 |" in res.payload and "12. Variação das Diárias" in res.payload


async def test_TWIN_either_text_alone_names_the_heading():
    for user, query in ((ASKED, ASKED), (REWRITE, REWRITE)):
        st, doc = await inn()
        acc = hybrid(st, user_text=user)
        await run(acc, query)
        rec = acc.records[0]
        assert len(rec.variants) == 1
        assert rec.outcome == OUTCOME_HITS and rec.heading_match == 1, (user, rec)


@pytest.mark.parametrize("typed", ["COMO FOI A VARIACAO DAS DIARIAS?",
                                   "e a variação da diária?",
                                   "Variação   das diárias, por favor"])
async def test_the_heading_is_read_through_the_general_fold(typed):
    # case, accents, spacing and the plural: «Diárias» and «diária» are one word to the tokenizer
    st, doc = await inn()
    acc = hybrid(st, user_text=typed)
    await run(acc, typed)
    rec = acc.records[0]
    assert rec.outcome == OUTCOME_HITS and rec.hit_ids == (kb(doc, 2),), (typed, rec)
    assert rec.heading_match == 1


# ── control: ONE word of a heading of several is not evidence (the mandatory mutation) ─

@pytest.mark.parametrize("question", ["Como foi a variação do câmbio?",
                                      "Quanto custam as diárias com café?"])
async def test_CONTROL_one_word_of_a_multi_word_heading_does_not_pass(question):
    st, doc = await inn()
    acc = hybrid(st, user_text=question)
    await run(acc, question)
    rec = acc.records[0]
    # the table WAS a candidate — the store returned it, under the floor like the other two
    assert rec.below_floor == 3
    assert rec.outcome == OUTCOME_NOTHING_RELEVANT and rec.cut_by == CUT_FLOOR, rec
    assert rec.heading_match == 0
    # and the same store, asked with BOTH words of the heading, does rescue it (the presence)
    twin = hybrid(st, user_text=ASKED)
    await run(twin, ASKED)
    assert twin.records[0].heading_match == 1


# ── control: a heading of ONE content word is never evidence ──────────────────────────

GENERIC = [
    ("Geral", "Estas condições valem para todas as reservas.", "Qual é a regra geral de cancelamento?"),
    ("Outros", "Aceitamos animais de pequeno porte.", "Quais são os outros serviços da pousada?"),
    # the PRICE of a floor over a list: a SPECIFIC one-word heading does not pass either
    ("Estacionamento", "Há vagas cobertas no subsolo.", "Tem estacionamento na pousada?"),
]


@pytest.mark.parametrize("heading, body, question", GENERIC)
async def test_CONTROL_a_one_word_heading_does_not_pass(heading, body, question, monkeypatch):
    st = store()
    doc = await publish(st, title=TITLE, chunks=[(body, (heading,), None, QUARTER)])
    acc = hybrid(st, user_text=question)
    await run(acc, question)
    rec = acc.records[0]
    assert rec.below_floor == 1
    assert rec.outcome == OUTCOME_NOTHING_RELEVANT and rec.cut_by == CUT_FLOOR, rec
    assert rec.heading_match == 0
    # the presence: every word of the heading IS in the question, so a floor of ONE word lets it in
    monkeypatch.setattr(cd, "MIN_HEADING_WORDS", 1)
    one = hybrid(st, user_text=question)
    await run(one, question)
    assert one.records[0].outcome == OUTCOME_HITS and one.records[0].hit_ids == (kb(doc, 0),)


def test_the_floor_of_words_is_two():
    assert cd.MIN_HEADING_WORDS == 2


# ── control: above the floor NOTHING changes — byte for byte against main ─────────────

# Digests of ``legacy_digest`` for each world, computed on ``main`` (d42aa6c, before this change)
# by running THIS file's worlds there. A world where the exception does not fire must reproduce
# the old bytes: the record (every old field), the payload and the evidence.
MAIN_DIGESTS = {
    "three_clear_and_a_heading_below":
        "323f801408727db4905948a5ae948957f42f18a8d4f55aa02598ab56fed50c7e",
    "the_heading_passage_clears_on_its_own":
        "b743b894ff45ce38a02cd3e50915e7f6962070e98c8e20c6f2a986def1d73a08",
    "nothing_names_a_heading":
        "5f5718c8e8ff0387f699b65e6c0bf7c6178fc74c221361282579dcb5c7b6b856",
    "nothing_relevant_by_the_floor":
        "5042c54f56f782731419ae1edf88b5dbcf49dcfa98e8ec60fd4b4d9456fb92f8",
}

ON_TOPIC = axis(0)
DIRECT = "Quais são as atividades de lazer?"
LEISURE = [
    ("Trilhas guiadas saem às 8h; a variação de horário é avisada.",
     ("6. Atividades de Lazer", "Trilhas"), None, ON_TOPIC),
    ("Caiaque no lago, com colete.", ("6. Atividades de Lazer", "Lago"), None, ON_TOPIC),
    ("Aulas de ioga ao nascer do sol.", ("6. Atividades de Lazer", "Ioga"), None, ON_TOPIC),
]


def _embedder(vectors):
    return KeyedEmbedder(vectors)


async def world(name: str):
    """``(access, query, document id)`` for the worlds the byte-identity controls read.
    ``DIRECT`` is embedded ON_TOPIC (``v = 1`` for the leisure passages)."""
    st = store()
    if name == "three_clear_and_a_heading_below":
        # the model's query fills all three slots from above the floor; the contact's words find
        # the table below it, under a heading they name — no slot is free, so nothing is added
        doc = await publish(st, title=TITLE, chunks=[*LEISURE, RATES])
        return hybrid(st, embedder=_embedder({DIRECT: ON_TOPIC}), user_text=ASKED), DIRECT, doc
    if name == "the_heading_passage_clears_on_its_own":
        doc = await publish(st, title=TITLE, chunks=[LOCATION, (TABLE, RATES[1], None, ON_TOPIC)])
        return hybrid(st, embedder=_embedder({ASKED: ON_TOPIC}), user_text=ASKED), ASKED, doc
    if name == "nothing_names_a_heading":
        doc = await publish(st, title=TITLE, chunks=[LEISURE[0], LOCATION, SERVICES])
        return hybrid(st, embedder=_embedder({DIRECT: ON_TOPIC}), user_text=DIRECT), DIRECT, doc
    if name == "nothing_relevant_by_the_floor":
        doc = await publish(st, title=TITLE, chunks=[LOCATION, SERVICES, RATES])
        return hybrid(st, user_text="Aceitam animais?"), "Aceitam animais?", doc
    raise AssertionError(name)


@pytest.mark.parametrize("name", sorted(MAIN_DIGESTS))
async def test_CONTROL_a_world_the_exception_does_not_touch_is_main_byte_for_byte(name):
    acc, question, doc = await world(name)
    res = await run(acc, question)
    rec = acc.records[0]
    assert getattr(rec, "heading_match", 0) == 0, rec
    assert "heading_match" not in " ".join(res.evidence)
    assert legacy_digest(rec, res, doc) == MAIN_DIGESTS[name], name


async def test_CONTROL_the_worlds_are_the_shapes_they_claim():
    # the four worlds above, read for what they are — so a digest cannot pin the wrong shape
    acc, q, doc = await world("three_clear_and_a_heading_below")
    await run(acc, q)
    rec = acc.records[0]
    assert rec.outcome == OUTCOME_HITS and len(rec.hit_ids) == 3 and min(rec.scores) >= FLOOR
    assert rec.below_floor == 1, "the table is there, under the floor"
    assert kb(doc, 3) not in rec.hit_ids
    acc, q, doc = await world("the_heading_passage_clears_on_its_own")
    await run(acc, q)
    rec = acc.records[0]
    assert rec.outcome == OUTCOME_HITS and rec.hit_ids == (kb(doc, 1),) and rec.scores[0] >= FLOOR
    acc, q, doc = await world("nothing_names_a_heading")
    await run(acc, q)
    assert acc.records[0].outcome == OUTCOME_HITS and acc.records[0].below_floor == 2
    acc, q, doc = await world("nothing_relevant_by_the_floor")
    await run(acc, q)
    rec = acc.records[0]
    assert rec.outcome == OUTCOME_NOTHING_RELEVANT and rec.cut_by == CUT_FLOOR
    assert rec.below_floor == 3


async def test_the_exception_only_APPENDS_after_what_cleared_the_floor(monkeypatch):
    st = store()
    doc = await publish(st, title=TITLE, chunks=[LEISURE[0], LOCATION, RATES])
    acc = hybrid(st, embedder=_embedder({ASKED: ON_TOPIC}), user_text=ASKED)
    res = await run(acc, ASKED)
    rec = acc.records[0]
    # the reference: the same world with the exception switched off
    monkeypatch.setattr(cd, "_heading_matches", lambda *a, **k: False)
    ref = hybrid(st, embedder=_embedder({ASKED: ON_TOPIC}), user_text=ASKED)
    await run(ref, ASKED)
    old = ref.records[0]
    assert old.outcome == OUTCOME_HITS and old.hit_ids == (kb(doc, 0),)
    # what cleared the floor keeps its place and its numbers; the table is ADDED after it
    assert rec.hit_ids == (kb(doc, 0), kb(doc, 2)) and rec.heading_match == 1
    assert rec.scores[:1] == old.scores and rec.lexical_scores[:1] == old.lexical_scores
    assert list(rec.scores) == sorted(rec.scores, reverse=True), "the order is the score's"
    assert rec.scores[-1] < FLOOR <= rec.scores[0]
    assert res.payload.index("Trilhas guiadas") < res.payload.index("| 2019 |")


# ── what the exception does NOT reach ─────────────────────────────────────────────────

async def test_a_LEXICAL_result_is_left_to_its_own_floor():
    st = store()
    await publish(st, title=TITLE, model=MODEL_B, chunks=[LOCATION, SERVICES, RATES])
    acc = hybrid(st, lexical_floor=0.9, user_text=ASKED)
    await run(acc, ASKED)
    rec = acc.records[0]
    assert rec.lexical and rec.outcome == OUTCOME_NOTHING_RELEVANT and rec.cut_by == CUT_FLOOR
    assert rec.heading_match == 0
    # the presence: the SAME documents on the hybrid scale — the heading lets the table in
    hy = store()
    await publish(hy, title=TITLE, chunks=[LOCATION, SERVICES, RATES])
    acc = hybrid(hy, user_text=ASKED)
    await run(acc, ASKED)
    assert acc.records[0].heading_match == 1


async def test_the_DOCUMENT_title_is_not_a_section_heading():
    st = store()
    # a passage under the document title alone: its path is the title and nothing else
    doc = await publish(st, title="Variação das Diárias", chunks=[(TABLE, (), None, QUARTER)])
    acc = hybrid(st, user_text=ASKED)
    await run(acc, ASKED)
    rec = acc.records[0]
    assert rec.below_floor == 1 and rec.outcome == OUTCOME_NOTHING_RELEVANT
    assert rec.heading_match == 0
    # the presence: the same words as a SECTION heading pass
    st2 = store()
    await publish(st2, title="Relatório", chunks=[(TABLE, ("Variação das Diárias",), None,
                                                    QUARTER)])
    acc2 = hybrid(st2, user_text=ASKED)
    await run(acc2, ASKED)
    assert acc2.records[0].heading_match == 1 and doc


async def test_the_words_must_be_in_ONE_text_not_spread_over_the_two():
    st, doc = await inn()
    # «variação» only in the contact's words, «diárias» only in the model's rewrite
    acc = hybrid(st, user_text="Como foi a variação?")
    await run(acc, "preço das diárias na alta temporada")
    rec = acc.records[0]
    assert len(rec.variants) == 2 and rec.below_floor == 3
    assert rec.outcome == OUTCOME_NOTHING_RELEVANT and rec.heading_match == 0, rec
    # the presence: the rewrite carrying both words
    acc = hybrid(st, user_text="Como foi a variação?")
    await run(acc, "variação das diárias na alta temporada")
    assert acc.records[0].heading_match == 1


async def test_a_passage_by_heading_still_faces_the_evidence_gate():
    st, doc = await inn()
    acc = hybrid(st, user_text=ASKED, lexical_evidence_floor=0.9)
    res = await run(acc, REWRITE)
    rec = acc.records[0]
    # it passed the floor by its heading, then the evidence gate cut the reading
    assert rec.heading_match == 1 and rec.hit_ids == ()
    assert rec.outcome == OUTCOME_NOTHING_RELEVANT and rec.cut_by == CUT_LEXICAL_EVIDENCE
    assert "Nothing in the documents" in res.payload


async def test_the_exception_fills_only_the_slots_the_floor_left():
    st = store()
    # four tables under the floor, each under a heading both texts name in full; the contact's
    # words find the first two, the model's rewrite (embedded on axis 4) the other two
    other = [0.0, 0.0, 0.0, math.sqrt(15.0), 1.0, 0.0, 0.0, 0.0]
    chunks = [(TABLE, (f"{n}. Variação das Diárias",), None, vec)
              for n, vec in ((10, QUARTER), (11, QUARTER), (12, other), (13, other))]
    doc = await publish(st, title=TITLE, chunks=chunks)
    acc = hybrid(st, embedder=_embedder({REWRITE: axis(4)}), user_text=ASKED, limit=2)
    await run(acc, REWRITE)
    rec = acc.records[0]
    assert rec.below_floor == 4, "four candidates, all under the floor, all named"
    assert rec.heading_match == 2 and rec.hit_ids == (kb(doc, 0), kb(doc, 1)) and rec.shown == 2


# ── SHAPES of the P9 ruler's controls — invented, NOT the ruler's data ────────────────
#
# The ruler itself (24 labelled questions over a reference host's documents) is run by the
# consultant before this lands; it reads a live store. These are the FORMS its two sets take,
# built here so the suite answers the same questions without it.

NEGATIVE_SHAPES = [
    # a question about something the documents do not hold, sharing ONE word of a heading
    "Tem variação de preço para crianças?",
    # naming the DOCUMENT's title words, not a section's
    "O relatório anual da pousada fala de animais?",
    # a heading's words split between the two texts (the rewrite below carries «diárias»)
    "Houve variação no número de hóspedes?",
    # a generic word that could head a section, alone
    "Quais são as regras gerais?",
]


@pytest.mark.parametrize("question", NEGATIVE_SHAPES)
async def test_SHAPE_a_negative_stays_nothing_relevant(question):
    st, doc = await inn()
    acc = hybrid(st, user_text=question)
    await run(acc, "diárias e hóspedes" if "hóspedes" in question else question)
    rec = acc.records[0]
    assert rec.outcome == OUTCOME_NOTHING_RELEVANT and rec.cut_by == CUT_FLOOR, (question, rec)
    assert rec.heading_match == 0


@pytest.mark.parametrize("name", ["three_clear_and_a_heading_below",
                                  "the_heading_passage_clears_on_its_own",
                                  "nothing_names_a_heading"])
async def test_SHAPE_a_positive_that_cleared_the_floor_does_not_get_worse(name, monkeypatch):
    acc, question, doc = await world(name)
    await run(acc, question)
    rec = acc.records[0]
    monkeypatch.setattr(cd, "_heading_matches", lambda *a, **k: False)
    ref, _, ref_doc = await world(name)
    await run(ref, question)
    old = ref.records[0]
    assert rec.outcome == old.outcome == OUTCOME_HITS
    new_ids = tuple(h.replace(doc, "DOC") for h in rec.hit_ids)
    old_ids = tuple(h.replace(ref_doc, "DOC") for h in old.hit_ids)
    assert new_ids[:len(old_ids)] == old_ids, "nothing lost, nothing reordered"
    assert rec.scores[:len(old.scores)] == old.scores
