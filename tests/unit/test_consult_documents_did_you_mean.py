"""``consult_documents`` — VQD-2(b): a *nothing relevant* carries the sections that may be meant.

The owner's order (29/09): instead of «I did not find it», «did you mean A or B?» — with options
taken ONLY from what the system read. Here the source is the passages a negative reading CUT: under
the floor, or rescued past it by the heading and cut by the evidence gate. Their section titles go
on the RECORD (``ConsultRecord.suggested_sections``) — a CLOSED list, at most
``MAX_SUGGESTED_SECTIONS`` distinct titles, each sharing at least one non-frame word with the
question (``cogno_anima.stages.scope_options.has_evidence``, the scope guard's own evidence rule).
The payload the executor reads stays the negative of always. ``section`` reads one of them by
title.

INVENTED data only — the estate, the family, the school and every figure are made up. What is
kept from the measured cases is their FORM:

* «details of the rents» — every passage under the floor, the right section's heading sharing the
  word «aluguel» with the contact's sentence (the bookkeeper's two real turns);
* «the evolution of the rents» — the right section RESCUED by its heading, then cut by the
  evidence gate (the twin the director decided today);
* «what do you know about <estate>?» with the literal sentence — a negative that offers the
  estate's sections while «sabe» is a subject word, and a READING of them once anima 0.1.1 lists
  it as a frame word (both worlds pinned: ``test_the_literal_subject_sentence_is_read_or_offered``);
* «is there parking?» — a TRUE negative: the passages back share no word with it, and nothing is
  offered.

The in-memory store's scale is not the Postgres one (see ``test_consult_documents_heading_inverse``):
what is kept is that every passage comes back under the floor.
"""

from __future__ import annotations

import math

import pytest

import cogno_cortex.skills.consult_documents as cd
from cogno_cortex import ToolContext
from cogno_cortex.skills.consult_documents import (
    CUT_FLOOR,
    CUT_LEXICAL_EVIDENCE,
    MAX_SUGGESTED_SECTIONS,
    META_DOCUMENTS_ACCESS,
    OUTCOME_HITS,
    OUTCOME_NOTHING_RELEVANT,
    ConsultDocumentsTool,
    DocumentsAccess,
    consult_documents_manifest,
    offer_consult_documents,
)
from tests.unit.documents_support import access, publish, store

FLOOR = 0.50
EVIDENCE = 0.13
QUARTER = [0.0, 0.0, 0.0, math.sqrt(15.0), 0.0, 0.0, 0.0, 1.0]
LOW = [0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0]

ESTATE = "Relatório patrimonial da Família Brandomar"
WEALTH = ("O patrimônio cresceu de R$ 1,2 mi para R$ 1,9 mi.", ("2. Evolução Patrimonial",),
          None, QUARTER)
INVESTMENT = ("| Ano | Aporte |\n|---|---|\n| 2019 | R$ 480.000 |", ("9. Quintarelo — Investimento",),
              None, LOW)
RENT = ("| Ano | Receita |\n|---|---|\n| 2023 | R$ 62.400 |",
        ("10. Quintarelo — Receita de Aluguel",), None, LOW)
EVOLUTION = ("| Ano | Loja | Apto |\n|---|---|---|\n| 2022 | 1.900 | 1.450 |",
             ("11. Evolução dos Aluguéis",), None, LOW)
DEPOSITS = ("| Inquilino | Caução |\n|---|---|\n| Loja | R$ 5.700 |", ("12. Cauções",), None, LOW)

SCHOOL = "Manual do estudante Vale Sereno"
BOOKS = ("A lista de livros do semestre.", ("Bibliografia",), None, QUARTER)
CORE_BOOKS = ("Os livros obrigatórios de cada disciplina.", ("Bibliografia Básica",), None, QUARTER)
CARD = ("A carteirinha é emitida na secretaria.", ("Carteirinha de estudante",), None, QUARTER)


async def estate(chunks=(WEALTH, INVESTMENT, RENT, EVOLUTION, DEPOSITS), **kw):
    st = store()
    doc = await publish(st, title=ESTATE, chunks=list(chunks), **kw)
    return st, doc


def kb(doc: str, ordinal: int) -> str:
    return f"kb:{doc}.1.{ordinal}"


def hybrid(st, **kw) -> DocumentsAccess:
    base = dict(hybrid_floor=FLOOR, lexical_floor=0.3, lexical_evidence_floor=EVIDENCE,
                suggest_sections=True)
    base.update(kw)
    return access(st, **base)


async def run(acc: DocumentsAccess, query: str = "", **args):
    tool = ConsultDocumentsTool(query=query, **args)
    return await tool.run(ToolContext(metadata={META_DOCUMENTS_ACCESS: acc}))


# The FORMS of the four measured negatives that had the answer under the floor — (the contact's
# words, the model's query, the section that held the answer).
RENTS_DETAILS = ("Traga os detalhes de alugueis",
                 "rental details: Quintarelo rental income, evolution of rents, and deposits",
                 "11. Evolução dos Aluguéis")
RENT_PER_UNIT = ("Qual o valor do aluguel por imóvel",
                 "Quintarelo rental value for each property or unit",
                 "10. Quintarelo — Receita de Aluguel")
LITERAL_SUBJECT = ("O que sabe sobre o Quintarelo?", "O que sabe sobre o Quintarelo?")


# ── the twins: the right section is offered ───────────────────────────────────────────

@pytest.mark.parametrize("asked, query, right", [RENTS_DETAILS, RENT_PER_UNIT],
                         ids=["rents_details", "rent_per_unit"])
async def test_TWIN_a_negative_under_the_floor_offers_the_section_that_held_the_answer(
        asked, query, right):
    st, _ = await estate()
    acc = hybrid(st, user_text=asked)
    res = await run(acc, query)
    rec = acc.records[0]
    assert rec.outcome == OUTCOME_NOTHING_RELEVANT and rec.cut_by == CUT_FLOOR, rec
    assert right in rec.suggested_sections, rec.suggested_sections
    assert 1 <= len(rec.suggested_sections) <= MAX_SUGGESTED_SECTIONS
    assert f"suggested={len(rec.suggested_sections)}" in res.evidence
    # the broken world, same store: the switch off — the negative of always, nothing offered
    off = hybrid(st, user_text=asked, suggest_sections=False)
    old = await run(off, query)
    assert off.records[0].suggested_sections == () and off.records[0].outcome == rec.outcome
    assert old.payload == res.payload, "the executor reads the SAME negative either way"
    assert old.evidence == [e for e in res.evidence if not e.startswith("suggested=")]


async def test_TWIN_rescued_by_the_heading_and_cut_by_the_evidence_gate_is_offered():
    # the director's twin: the heading rescues the right section from under the floor, and the
    # evidence gate then cuts the whole reading — the section is a CANDIDATE, never an answer
    st, _ = await estate()
    asked = "Como foi a evolução dos aluguéis?"
    acc = hybrid(st, user_text=asked, lexical_evidence_floor=0.9)
    await run(acc, "evolução dos aluguéis do Quintarelo")
    rec = acc.records[0]
    assert rec.cut_by == CUT_LEXICAL_EVIDENCE and rec.heading_match >= 1, rec
    assert rec.suggested_sections[0] == "11. Evolução dos Aluguéis", rec.suggested_sections
    # the presence of the other side: the gate off reads that section (it is no negative)
    read = hybrid(st, user_text=asked)
    await run(read, "evolução dos aluguéis do Quintarelo")
    assert read.records[0].outcome == OUTCOME_HITS and read.records[0].suggested_sections == ()


@pytest.mark.parametrize("frame_verb", [True, False], ids=["sabe_is_frame", "sabe_is_subject"])
async def test_the_literal_subject_sentence_is_read_or_offered_never_lost(frame_verb, monkeypatch):
    # The third measured shape, the contact's LITERAL sentence «O que sabe sobre <estate>?». What
    # it does hangs on ONE word of the shared frame-word list, so both worlds are pinned here
    # whatever anima is installed: with «sabe» a frame word (anima 0.1.1) the sentence's one
    # subject word heads two sections and the inverse heading test READS them — hits, nothing
    # offered; with «sabe» a subject word (the anima before) it is a negative, and the section
    # that answers is OFFERED. Either way the contact is not left with «I did not find it».
    prefixes = (cd._GENERIC_PREFIXES | {"sabe"}) if frame_verb else (cd._GENERIC_PREFIXES
                                                                       - {"sabe"})
    monkeypatch.setattr(cd, "_GENERIC_PREFIXES", prefixes)
    st, doc = await estate()
    acc = hybrid(st, user_text=LITERAL_SUBJECT[0])
    await run(acc, LITERAL_SUBJECT[1])
    rec = acc.records[0]
    if frame_verb:
        assert rec.outcome == OUTCOME_HITS and rec.heading_match >= 1, rec
        assert set(rec.hit_ids) <= {kb(doc, 1), kb(doc, 2)} and rec.suggested_sections == ()
    else:
        assert rec.outcome == OUTCOME_NOTHING_RELEVANT and rec.cut_by == CUT_FLOOR, rec
        assert "9. Quintarelo — Investimento" in rec.suggested_sections, rec.suggested_sections


# ── the true negative: nothing is offered ─────────────────────────────────────────────

async def test_CONTROL_parking_is_a_true_negative_and_offers_nothing():
    st = store()
    await publish(st, title=SCHOOL, chunks=[BOOKS, CORE_BOOKS, CARD])
    asked = "Tem estacionamento no local?"
    acc = hybrid(st, user_text=asked)
    res = await run(acc, "availability of parking at the location")
    rec = acc.records[0]
    assert rec.below_floor == 3, "the three passages WERE candidates, under the floor"
    assert rec.outcome == OUTCOME_NOTHING_RELEVANT and rec.suggested_sections == (), rec
    assert not any(e.startswith("suggested=") for e in res.evidence)


async def test_CONTROL_a_frame_word_alone_is_no_evidence():
    # «estudante» is a business's FRAME word (GENERIC_SUBJECT_WORDS): «Carteirinha de estudante»
    # does not become an option for a question about another student matter
    st = store()
    await publish(st, title=SCHOOL, chunks=[BOOKS, CORE_BOOKS, CARD])
    asked = "Qual o horário do estudante?"
    acc = hybrid(st, user_text=asked)
    await run(acc, asked)
    rec = acc.records[0]
    assert rec.outcome == OUTCOME_NOTHING_RELEVANT and rec.suggested_sections == (), rec


async def test_CONTROL_the_numbering_of_the_outline_is_no_evidence():
    # «11» is in «11. Evolução dos Aluguéis» and in the question; it says nothing about rents
    st, _ = await estate()
    asked = "O que houve na reunião 11?"
    acc = hybrid(st, user_text=asked)
    await run(acc, asked)
    rec = acc.records[0]
    assert rec.outcome == OUTCOME_NOTHING_RELEVANT, rec
    assert "11. Evolução dos Aluguéis" not in rec.suggested_sections, rec.suggested_sections


async def test_CONTROL_a_passage_under_the_document_title_alone_offers_nothing():
    st = store()
    await publish(st, title="Aluguéis do Quintarelo", chunks=[("Sem seções.", (), None, LOW)])
    acc = hybrid(st, user_text="Traga os detalhes de alugueis")
    await run(acc, "rental details")
    rec = acc.records[0]
    assert rec.outcome == OUTCOME_NOTHING_RELEVANT and rec.suggested_sections == (), rec


# ── the property: every option is a title the reading returned ───────────────────────

QUESTIONS = [RENTS_DETAILS[:2], RENT_PER_UNIT[:2], LITERAL_SUBJECT,
             ("Quanto rendeu o Quintarelo?", "Quintarelo income"),
             ("E as cauções?", "deposits"), ("evolução", "evolution"),
             ("Tem estacionamento?", "parking")]


@pytest.mark.parametrize("asked, query", QUESTIONS)
async def test_PROPERTY_every_option_is_a_section_title_of_a_passage_the_reading_returned(
        asked, query, monkeypatch):
    st, _ = await estate()
    returned: "list[str]" = []
    real = cd._fuse

    def spy(results, *, lexical):
        fused = real(results, lexical=lexical)
        returned.extend(cd._label(cd._section_title(f.hit), cd._names(())) for f in fused)
        return fused

    monkeypatch.setattr(cd, "_fuse", spy)
    acc = hybrid(st, user_text=asked)
    await run(acc, query)
    offered = acc.records[0].suggested_sections
    assert set(offered) <= set(returned), (offered, returned)
    assert len(offered) == len(set(offered)) <= MAX_SUGGESTED_SECTIONS


# ── the ceiling, and the filter, as MUTATIONS written as tests ────────────────────────

async def test_the_ceiling_is_three_even_when_more_titles_share_the_word():
    chunks = [(f"Tabela {i}.", (f"{i}. Aluguel da unidade {i}",), None, LOW) for i in range(1, 7)]
    st = store()
    await publish(st, title=ESTATE, chunks=chunks)
    acc = hybrid(st, user_text="Traga os detalhes de alugueis", limit=6)
    await run(acc, "rental details")
    rec = acc.records[0]
    assert rec.below_floor == 6, "six candidates, every one sharing «aluguel»"
    assert len(rec.suggested_sections) == MAX_SUGGESTED_SECTIONS == 3, rec.suggested_sections


async def test_the_filter_is_what_keeps_the_unrelated_sections_out(monkeypatch):
    st, _ = await estate()
    acc = hybrid(st, user_text=RENTS_DETAILS[0])
    await run(acc, RENTS_DETAILS[1])
    kept = acc.records[0].suggested_sections
    assert "12. Cauções" not in kept and "2. Evolução Patrimonial" not in kept, kept
    # the presence: with the evidence rule answering yes to everything, they come in
    monkeypatch.setattr(cd, "has_evidence", lambda message, option: True)
    bulk = hybrid(st, user_text=RENTS_DETAILS[0])
    await run(bulk, RENTS_DETAILS[1])
    assert set(bulk.records[0].suggested_sections) - set(kept), bulk.records[0]


def test_the_evidence_rule_is_the_scope_guards_not_a_copy():
    from cogno_anima.stages import scope_options
    assert cd.has_evidence is scope_options.has_evidence


# ── «sim, A»: the section is read by its title ────────────────────────────────────────

async def test_TWIN_the_chosen_section_is_read_by_its_title_without_a_floor():
    st, doc = await estate()
    acc = hybrid(st, user_text="sim, a evolução dos aluguéis")
    res = await run(acc, "evolução dos aluguéis", section="11. Evolução dos Aluguéis")
    rec = acc.records[0]
    assert rec.outcome == OUTCOME_HITS and rec.section_requested, rec
    assert rec.hit_ids == (kb(doc, 3),), "that section, only"
    assert rec.embedding_calls == 0 and acc.embedder.calls == [], "no embedding for a title"
    assert "| 2022 | 1.900 | 1.450 |" in res.payload
    assert "11. Evolução dos Aluguéis" in res.payload, "with its provenance"
    # the broken world: the switch off — `section` is an ignored extra and the query is searched
    off = hybrid(st, user_text="sim, a evolução dos aluguéis", suggest_sections=False)
    await run(off, "evolução dos aluguéis", section="11. Evolução dos Aluguéis")
    assert not off.records[0].section_requested and off.records[0].embedding_calls >= 1


@pytest.mark.parametrize("typed", ["11. evolução dos alugueis", "11 Evolução  dos Aluguéis",
                                   " 11. EVOLUÇÃO DOS ALUGUÉIS "])
async def test_the_title_is_compared_through_the_general_fold(typed):
    st, doc = await estate()
    acc = hybrid(st)
    await run(acc, "x", section=typed)
    assert acc.records[0].hit_ids == (kb(doc, 3),), typed


@pytest.mark.parametrize("typed", ["Evolução dos Aluguéis", "11. Evolução", "Aluguéis"])
async def test_a_title_that_is_not_the_whole_title_reads_nothing(typed):
    st, _ = await estate()
    acc = hybrid(st)
    res = await run(acc, "x", section=typed)
    rec = acc.records[0]
    assert rec.outcome == OUTCOME_NOTHING_RELEVANT and rec.section_requested, rec
    assert "No section with that title" in res.payload


async def test_a_section_of_a_document_this_reader_cannot_read_reads_nothing():
    st = store()
    await publish(st, title=ESTATE, chunks=[EVOLUTION], profiles=("ADMIN",))
    acc = hybrid(st)          # the reader is EMPLOYEE
    res = await run(acc, "x", section="11. Evolução dos Aluguéis")
    assert acc.records[0].outcome == OUTCOME_NOTHING_RELEVANT
    assert "1.900" not in res.payload


async def test_every_passage_of_the_section_is_read_and_no_other():
    second = ("| 2024 | 2.050 | 1.600 |", ("11. Evolução dos Aluguéis",), None, LOW)
    st, doc = await estate(chunks=(WEALTH, EVOLUTION, second, DEPOSITS))
    acc = hybrid(st)
    res = await run(acc, "x", section="11. Evolução dos Aluguéis")
    assert set(acc.records[0].hit_ids) == {kb(doc, 1), kb(doc, 2)}
    assert "1.450" in res.payload and "1.600" in res.payload and "5.700" not in res.payload


# ── off: today, byte for byte ─────────────────────────────────────────────────────────

def test_OFF_the_schema_is_todays_and_ON_only_adds_section():
    today = consult_documents_manifest("d").parameters
    assert consult_documents_manifest("d", sections=False).parameters == today
    on = consult_documents_manifest("d", sections=True).parameters
    assert set(on["properties"]) - set(today["properties"]) == {"section"}
    assert {k: v for k, v in on["properties"].items() if k != "section"} == today["properties"]
    assert on["required"] == today["required"] == ["query"]


async def test_the_offered_manifest_carries_section_only_when_the_access_suggests():
    st, _ = await estate()
    off = await offer_consult_documents(hybrid(st, suggest_sections=False))
    on = await offer_consult_documents(hybrid(st))
    assert "section" not in off.parameters["properties"]
    assert "section" in on.parameters["properties"]


def test_suggest_sections_must_be_a_bool():
    st = store()
    with pytest.raises(TypeError):
        hybrid(st, suggest_sections="yes")


async def test_hits_never_carry_suggestions():
    st, _ = await estate()
    acc = hybrid(st, user_text="Quintarelo")
    await run(acc, "Quintarelo")
    rec = acc.records[0]
    assert rec.outcome == OUTCOME_HITS and rec.suggested_sections == (), rec


async def test_a_store_that_raises_on_a_section_read_is_an_error_never_an_absence():
    from tests.unit.documents_support import SpyStore
    st, _ = await estate()
    acc = hybrid(SpyStore(st, fail=True))
    res = await run(acc, "x", section="11. Evolução dos Aluguéis")
    assert res.status == "error" and "do not treat this as" in res.payload
    assert acc.records[0].outcome == "search_failed" and acc.records[0].section_requested
