"""``consult_documents`` — the heading test, the INVERSE direction: the question IN the heading.

The direct direction (``test_consult_documents_heading_evidence.py``) lets a passage below the
hybrid floor in when EVERY content word of its section heading is in the question, and the heading
has at least ``MIN_HEADING_WORDS``. A SHORT question that names its subject never meets that: the
heading «9. Quintarelo — Investimento» carries a word the question «Quintarelo?» does not. So the
other direction: EVERY subject word of the question (its content words minus digits and minus the
business's frame words, ``cogno_anima.stages.scope_options.GENERIC_SUBJECT_WORDS``) is in the
heading, and the question has at least ONE.

INVENTED data only — the estate, the names and the figures are made up. What is kept from the
measured case is its FORM: a one-word question naming the subject, the store returning three
passages ALL under the hybrid floor (``nothing_relevant``, ``cut_by=floor``), and the document
holding two sections whose heading carries that word.

The in-memory store's lexical measure is the share of the question's distinct words a passage
carries (its content starts with its heading path, the document title included); the fused score
is ``0.6·v + 0.4·l``. That measure gives a ONE-word question ``l = 1`` on every passage whose
heading carries the word — the real store's ``ts_rank_cd`` does not, which is why the measured
reading came back under the floor. So the sections a question's subject heads are embedded
``LOW`` (orthogonal to ``NEUTRAL``, ``v = 0``: at most ``0.4·l ≤ 0.40``) and the others
``QUARTER`` (``v = 0.25``: ``0.15 + 0.4·l``), and the floor here is ``0.50`` — NOT the host's
0.40, because this store's scale is not the Postgres one; what is kept is the FORM, every passage
returned under the floor.
"""

from __future__ import annotations

import math

import pytest

import cogno_cortex.skills.consult_documents as cd
from cogno_cortex import ToolContext
from cogno_cortex.skills.consult_documents import (
    CUT_FLOOR,
    META_DOCUMENTS_ACCESS,
    OUTCOME_HITS,
    OUTCOME_NOTHING_RELEVANT,
    ConsultDocumentsTool,
    DocumentsAccess,
)
from tests.unit.documents_support import access, publish, store

FLOOR = 0.50
EVIDENCE = 0.13
QUARTER = [0.0, 0.0, 0.0, math.sqrt(15.0), 0.0, 0.0, 0.0, 1.0]
LOW = [0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0]

TITLE = "Relatório patrimonial da Família Brandomar"
SUBJECT = "Quintarelo"

INVESTMENT = ("| Ano | Aporte |\n|---|---|\n| 2019 | R$ 480.000 |\n| 2022 | R$ 95.000 |",
              ("9. Quintarelo — Investimento",), None, LOW)
RENT = ("| Ano | Aluguel anual |\n|---|---|\n| 2023 | R$ 62.400 |\n| 2024 | R$ 66.000 |",
        ("10. Quintarelo — Receita de Aluguel",), None, LOW)
INTERNET = ("A rede da casa principal chama-se Brandomar-Casa; a senha fica com o caseiro.",
            ("4. Casa Principal — Serviços",), None, QUARTER)
GARDEN = ("O jardim é mantido às terças e sextas.", ("5. Jardim e Pomar",), None, QUARTER)


async def estate(chunks=(GARDEN, INTERNET, INVESTMENT, RENT)):
    st = store()
    doc = await publish(st, title=TITLE, chunks=list(chunks))
    return st, doc


def kb(doc: str, ordinal: int) -> str:
    return f"kb:{doc}.1.{ordinal}"


def hybrid(st, **kw) -> DocumentsAccess:
    base = dict(hybrid_floor=FLOOR, lexical_floor=0.3, lexical_evidence_floor=EVIDENCE)
    base.update(kw)
    return access(st, **base)


async def run(acc: DocumentsAccess, query: str):
    tool = ConsultDocumentsTool(query=query)
    return await tool.run(ToolContext(metadata={META_DOCUMENTS_ACCESS: acc}))


def no_inverse(monkeypatch) -> None:
    """The tree before this change: the subject of a question is never read."""
    monkeypatch.setattr(cd, "_subject_words", lambda question: frozenset())


# ── the twin: the FORM of the measured case ───────────────────────────────────────────

async def test_TWIN_a_one_word_question_reads_the_two_sections_its_subject_heads(monkeypatch):
    st, doc = await estate()
    acc = hybrid(st, user_text=SUBJECT)
    res = await run(acc, SUBJECT)
    rec = acc.records[0]
    assert rec.outcome == OUTCOME_HITS and rec.cut_by is None, rec
    assert set(rec.hit_ids) == {kb(doc, 2), kb(doc, 3)}, "the two Quintarelo sections, only"
    assert rec.heading_match == 2
    assert all(s < FLOOR for s in rec.scores), "both came from under the floor"
    assert "| 2022 | R$ 95.000 |" in res.payload and "| 2024 | R$ 66.000 |" in res.payload
    assert "heading_match=2" in res.evidence
    # the broken world, same store: three passages back, all under the floor, nothing relevant
    no_inverse(monkeypatch)
    old = hybrid(st, user_text=SUBJECT)
    await run(old, SUBJECT)
    rec = old.records[0]
    assert rec.outcome == OUTCOME_NOTHING_RELEVANT and rec.cut_by == CUT_FLOOR, rec
    assert rec.below_floor == 3 and rec.heading_match == 0


async def test_TWIN_the_contact_asks_in_a_sentence_and_the_model_queries_the_subject():
    # the measured trace's split: the EGO's query is the bare subject; the contact wrote a sentence
    st, doc = await estate()
    acc = hybrid(st, user_text=f"O que sabe sobre o {SUBJECT}?")
    await run(acc, SUBJECT)
    rec = acc.records[0]
    assert len(rec.variants) == 2
    assert rec.outcome == OUTCOME_HITS and rec.heading_match == 2, rec


@pytest.mark.parametrize("typed", ["quintarelo", "Quintarelo?", "QUINTARELO!",
                                   "Quintarelo 2023"])
async def test_the_subject_is_read_through_the_fold_and_without_digits(typed):
    st, doc = await estate()
    acc = hybrid(st, user_text=typed)
    await run(acc, typed)
    rec = acc.records[0]
    assert rec.outcome == OUTCOME_HITS and rec.heading_match == 2, (typed, rec)


async def test_a_two_word_subject_inside_one_heading_passes():
    st, doc = await estate()
    acc = hybrid(st, user_text="Receita do Quintarelo?")
    await run(acc, "Receita do Quintarelo?")
    rec = acc.records[0]
    assert rec.outcome == OUTCOME_HITS and rec.hit_ids == (kb(doc, 3),), rec
    assert rec.heading_match == 1


# ── the DECLARED LIMIT: a frame verb the shared list does not carry ───────────────────

async def test_LIMIT_the_literal_sentence_with_sabe_is_not_rescued_by_itself():
    # «sabe» is a content word to the engram's tokenizer and is not in GENERIC_SUBJECT_WORDS
    # («saber» is; at the 6-character prefix «sabe» is not «saber»), so the contact's sentence
    # ALONE names a word no heading carries. It is rescued when the model's query names the
    # subject (the twin above). The conjugations belong in the shared list (anima) — a follow-up.
    # When that lands this test fails, and it should be rewritten as a twin.
    st, doc = await estate()
    sentence = f"O que sabe sobre o {SUBJECT}?"
    acc = hybrid(st, user_text=sentence)
    await run(acc, sentence)
    rec = acc.records[0]
    assert len(rec.variants) == 1
    assert rec.outcome == OUTCOME_NOTHING_RELEVANT and rec.heading_match == 0, rec
    assert cd._subject_words(cd.lexical_terms(sentence)) == {"sabe", "quintarelo"}


# ── control (a): a GENERIC one-word question lifts no section ─────────────────────────

SCHOOL = [
    ("Matrículas abertas de janeiro a março.", ("2. Escola — Matrículas",), None, LOW),
    ("O uniforme é obrigatório.", ("3. Escola — Regras",), None, LOW),
    ("Aulas de segunda a sexta.", ("4. Escola — Horários",), None, LOW),
]


@pytest.mark.parametrize("question, word", [("Escola?", "Escola"), ("escolas", "Escola"),
                                            ("Documentos?", "Documentos"),
                                            ("E a empresa?", "Empresa")])
async def test_CONTROL_a_generic_one_word_question_rescues_nothing(question, word, monkeypatch):
    st = store()
    chunks = [(body, (trail[0].replace("Escola", word),), page, vec)
              for body, trail, page, vec in SCHOOL]
    await publish(st, title="Guia Pinhal Alto", chunks=chunks)
    acc = hybrid(st, user_text=question)
    await run(acc, question)
    rec = acc.records[0]
    assert rec.below_floor == 3, "the three sections WERE candidates, under the floor"
    assert rec.outcome == OUTCOME_NOTHING_RELEVANT and rec.cut_by == CUT_FLOOR, rec
    assert rec.heading_match == 0
    # the presence: with the frame words switched off, the same question lifts all three
    monkeypatch.setattr(cd, "_GENERIC_PREFIXES", frozenset())
    bulk = hybrid(st, user_text=question)
    await run(bulk, question)
    assert bulk.records[0].heading_match == 3, (question, bulk.records[0])


async def test_CONTROL_a_question_of_stopwords_only_rescues_nothing(monkeypatch):
    st, doc = await estate()
    acc = hybrid(st, user_text="O que é isso?")
    await run(acc, "O que é isso?")
    rec = acc.records[0]
    assert rec.outcome == OUTCOME_NOTHING_RELEVANT and rec.heading_match == 0, rec
    assert cd._subject_words(cd.lexical_terms("O que é isso?")) == set()


def test_the_frame_words_are_the_shared_list_not_a_new_one():
    from cogno_anima.stages.scope_options import EVIDENCE_PREFIX, GENERIC_SUBJECT_WORDS
    assert cd._GENERIC_PREFIXES == cd.lexical_terms(GENERIC_SUBJECT_WORDS, EVIDENCE_PREFIX)
    assert {"escola", "docume", "empres"} <= cd._GENERIC_PREFIXES


# ── control (b): the Wi-Fi password reads nothing ─────────────────────────────────────

@pytest.mark.parametrize("question", ["Qual a senha do Wi-Fi?", "senha do wifi", "Wi-Fi?"])
async def test_CONTROL_the_wifi_password_rescues_nothing(question):
    st, doc = await estate()
    acc = hybrid(st, user_text=question)
    await run(acc, question)
    rec = acc.records[0]
    assert rec.below_floor >= 1, "the store DID return passages, under the floor"
    assert rec.outcome == OUTCOME_NOTHING_RELEVANT and rec.cut_by == CUT_FLOOR, rec
    assert rec.heading_match == 0


async def test_CONTROL_a_subject_word_must_be_in_the_heading_not_only_the_body():
    # «Brandomar» is in the INTERNET body and the document TITLE, never a section heading
    st, doc = await estate()
    acc = hybrid(st, user_text="Brandomar?")
    await run(acc, "Brandomar?")
    rec = acc.records[0]
    assert rec.below_floor >= 1 and rec.heading_match == 0, rec
    assert all(s >= FLOOR for s in rec.scores), "whatever passed, passed on its own score"


async def test_CONTROL_one_subject_word_missing_from_the_heading_is_not_enough():
    st, doc = await estate()
    acc = hybrid(st, user_text="Despesas do Quintarelo?")
    await run(acc, "Despesas do Quintarelo?")
    rec = acc.records[0]
    assert rec.outcome == OUTCOME_NOTHING_RELEVANT and rec.heading_match == 0, rec


# ── what the inverse does NOT change ──────────────────────────────────────────────────

async def test_it_only_fills_the_slots_the_floor_left():
    st, doc = await estate()
    acc = hybrid(st, user_text=SUBJECT, limit=1)
    await run(acc, SUBJECT)
    rec = acc.records[0]
    assert rec.heading_match == 1 and len(rec.hit_ids) == 1

async def test_RESCUED_AND_CUT_the_record_says_both_heading_match_and_cut_by():
    # The shape the Postgres leg predicts for a TABLE named only in its heading: the inverse lifts
    # it from under the floor, then the evidence gate (unchanged) cuts the reading. The record and
    # the evidence line carry BOTH sides, so a ruler reading them tells «rescued, then cut by the
    # gate» from «never rescued» (cut_by=floor, heading_match=0).
    st, doc = await estate(chunks=(GARDEN, INTERNET, INVESTMENT))
    acc = hybrid(st, user_text="Quintarelo 2023", lexical_evidence_floor=0.9)
    res = await run(acc, "Quintarelo 2023")
    rec = acc.records[0]
    assert rec.heading_match == 1 and rec.cut_by == "lexical_evidence", rec
    assert rec.outcome == OUTCOME_NOTHING_RELEVANT and rec.hit_ids == ()
    assert rec.lexical_evidence == 0.5, "the rescued table carries one of the two words"
    assert "heading_match=1" in res.evidence and "cut_by=lexical_evidence" in res.evidence
    # the presence: the same store with the gate off reads the table it rescued
    off = hybrid(st, user_text="Quintarelo 2023", lexical_evidence_floor=0.0)
    await run(off, "Quintarelo 2023")
    assert off.records[0].outcome == OUTCOME_HITS and off.records[0].hit_ids == (kb(doc, 2),)
    assert off.records[0].heading_match == 1 and off.records[0].cut_by is None


# The lexical-result guard is the SAME code the direct direction goes through (the inverse lives
# inside ``_heading_matches``, called only in hybrid mode); test_consult_documents_heading_evidence.py
# pins it.
