"""``consult_documents`` — the second gate in HYBRID mode: lexical EVIDENCE.

Among the passages that CLEAR the hybrid floor, at least one must share the question's words
(``lexical_score >= DocumentsAccess.lexical_evidence_floor``), or the reading is *nothing
relevant* with ``cut_by="lexical_evidence"``. Over the REAL in-memory store, INVENTED data.

Every absence carries its CONTROL — the same world with the gate off (``0``) produces the
presence first — and the declared PRICE is produced, not described: a passage that answers by
paraphrase alone, with no word in common, now falls to *nothing relevant*.

The in-memory store's lexical measure is the share of the question's distinct words a passage
carries (``cogno_engram``'s stand-in); the fused score is ``0.6·v + 0.4·l``. Vectors are the
axes of ``documents_support`` — a question embedded like a passage has ``v = 1``.
"""

from __future__ import annotations

import pytest

from cogno_cortex import ToolContext
from cogno_cortex.skills.consult_documents import (
    CUT_FLOOR,
    CUT_LEXICAL_EVIDENCE,
    META_DOCUMENTS_ACCESS,
    OUTCOME_HITS,
    OUTCOME_NOTHING_RELEVANT,
    VALID_CUTS,
    ConsultDocumentsTool,
    DocumentsAccess,
)
from tests.unit.documents_support import (
    MODEL_A,
    MODEL_B,
    NEUTRAL,
    OWNER,
    KeyedEmbedder,
    access,
    axis,
    publish,
    store,
)

# The answer, and a question that PARAPHRASES it — not one word in common (the in-memory store
# keeps every word, stopwords included, so the paraphrase is written to share none at all).
SAT = ("We open from 8 to 12 on Saturday.", ("Timetable", "Saturday"), 4, NEUTRAL)
PARAPHRASE = "weekend hours"
ABOUT = axis(0)


async def run(acc: DocumentsAccess, query: str):
    tool = ConsultDocumentsTool(query=query)
    return await tool.run(ToolContext(metadata={META_DOCUMENTS_ACCESS: acc}))


# ── the price, PRODUCED: a paraphrase with no word in common is cut ──────────────────

async def test_PRICE_a_paraphrase_with_no_common_word_falls_to_nothing_relevant():
    st = store()
    await publish(st, chunks=[SAT])
    # the CONTROL first: the gate off, the paraphrase clears the hybrid floor on topic alone
    # (v = 1 → 0.6·1 + 0.4·0 = 0.6 ≥ 0.5) and the passage is shown
    off = access(st, lexical_evidence_floor=0.0)
    res = await run(off, PARAPHRASE)
    assert off.records[0].outcome == OUTCOME_HITS and "We open" in res.payload
    assert off.records[0].scores == (0.6,) and off.records[0].lexical_scores == (0.0,)
    # the gate on: the same passage, the same score — and nothing shares a word with the question
    on = access(st, lexical_evidence_floor=0.1)
    res = await run(on, PARAPHRASE)
    rec = on.records[0]
    assert rec.outcome == OUTCOME_NOTHING_RELEVANT and "We open" not in res.payload
    assert rec.cut_by == CUT_LEXICAL_EVIDENCE and rec.lexical_evidence == 0.0
    assert rec.below_floor == 0, "it cleared the floor — the floor did NOT cut it"
    assert "cut_by=lexical_evidence" in res.evidence and "lexical_evidence=0" in res.evidence


# ── the gate is on the SET that cleared the floor, never on its first passage ─────────

async def test_a_word_in_ANY_passage_that_cleared_the_floor_lets_the_reading_through():
    st = store()
    # A — on topic, no word in common: v = 1, l = 0 → 0.6.
    # B — shares «parking» (1 of the question's 2 words) and is weaker on topic:
    #     v = cos(B, NEUTRAL) = 1/√(1.2² + 1) ≈ 0.640, l = 0.5 → ≈ 0.584.
    # Both clear a 0.5 floor, A FIRST — so a gate that read only the first passage would cut.
    near = [1.2, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0]
    await publish(st, chunks=[
        ("We open from 8 to 12 on Saturday.", ("Timetable", "Saturday"), 4, NEUTRAL),
        ("Parking is free for students.", ("Parking",), 5, near),
    ])
    q = "weekend parking"
    off, on = access(st, lexical_evidence_floor=0.0), access(st, lexical_evidence_floor=0.4)
    res_off, res_on = await run(off, q), await run(on, q)
    a, b = off.records[0], on.records[0]
    # the first passage (the Saturday one) has no word in common; the second carries 1 of 2
    assert b.outcome == OUTCOME_HITS and b.cut_by is None and b.lexical_evidence == 0.5
    # the gate only DECIDES: the same passages, in the same order, with the same scores
    assert (b.hit_ids, b.scores, b.lexical_scores) == (a.hit_ids, a.scores, a.lexical_scores)
    assert res_on.payload == res_off.payload
    assert b.lexical_scores == (0.0, 0.5), "A (no word) first, B (the word) second"
    assert b.scores[0] > b.scores[1] >= 0.5


async def test_a_word_only_BELOW_the_floor_is_not_evidence():
    st = store()
    await publish(st, chunks=[
        ("We open from 8 to 12 on Saturday.", ("Timetable", "Saturday"), 4, NEUTRAL),
        ("Parking is free for students.", ("Parking",), 5, ABOUT),     # v = 0 for the question
    ])
    q = "weekend parking"
    # the parking passage: v = 0, l = 0.5 → 0.2, below a 0.5 floor; only the Saturday one clears
    off = access(st, lexical_evidence_floor=0.0)
    await run(off, q)
    assert off.records[0].outcome == OUTCOME_HITS and off.records[0].below_floor == 1  # CONTROL
    on = access(st, lexical_evidence_floor=0.4)
    await run(on, q)
    rec = on.records[0]
    assert rec.outcome == OUTCOME_NOTHING_RELEVANT and rec.cut_by == CUT_LEXICAL_EVIDENCE
    assert rec.lexical_evidence == 0.0, "the word that counted lives below the floor"


# ── which gate cut it, always said; the lexical scale is untouched ────────────────────

async def test_nothing_clearing_the_floor_is_cut_by_the_FLOOR():
    st = store()
    await publish(st, chunks=[("Parking is free.", ("Parking",), 5, ABOUT)])
    acc = access(st, hybrid_floor=0.5, lexical_evidence_floor=0.4)
    await run(acc, "saturday")                           # v = 0, l = 0 → nothing clears
    rec = acc.records[0]
    assert rec.outcome == OUTCOME_NOTHING_RELEVANT and rec.cut_by == CUT_FLOOR
    assert rec.lexical_evidence is None
    assert VALID_CUTS == {CUT_FLOOR, CUT_LEXICAL_EVIDENCE}


async def test_a_reading_with_hits_says_no_cut_and_carries_its_evidence():
    st = store()
    await publish(st, chunks=[SAT])
    acc = access(st, lexical_evidence_floor=0.4)
    await run(acc, "saturday sunday")                    # l = 1/2
    rec = acc.records[0]
    assert rec.outcome == OUTCOME_HITS and rec.cut_by is None and rec.lexical_evidence == 0.5
    assert len(rec.lexical_scores) == len(rec.scores) == len(rec.hit_ids)


async def test_a_LEXICAL_result_is_not_held_to_the_evidence_gate():
    """On the lexical scale the floor already IS a lexical threshold: the gate stays out."""
    st = store()
    await publish(st, model=MODEL_B, chunks=[SAT])     # indexed by another model → words only
    acc = access(st, hybrid_floor=0.9, lexical_floor=0.3, lexical_evidence_floor=0.9)
    res = await run(acc, "saturday sunday")             # l = 0.5 ≥ 0.3, < 0.9
    rec = acc.records[0]
    assert rec.lexical and rec.outcome == OUTCOME_HITS and "We open" in res.payload
    assert rec.cut_by is None and rec.lexical_evidence is None


# ── the fold is the STORE's: «Sábado» and «sabado» are the same evidence ───────────────

@pytest.mark.parametrize("typed", ["sábado", "sabado", "SÁBADO"])
async def test_the_evidence_reads_through_the_stores_fold(typed):
    st = store()
    await publish(st, chunks=[("Abrimos das 8h às 12h.", ("Horários", "Sábado"), 3, NEUTRAL)])
    acc = access(st, lexical_evidence_floor=0.5)
    await run(acc, typed)
    rec = acc.records[0]
    # the heading carries «Sábado»; the store folds case and accents on both sides
    assert rec.outcome == OUTCOME_HITS and rec.lexical_evidence == 1.0, (typed, rec)


# ── required, like the two floors ─────────────────────────────────────────────────────

def test_the_evidence_floor_has_no_default():
    with pytest.raises(TypeError):
        DocumentsAccess(store=store(), embedder=KeyedEmbedder(), embed_model=MODEL_A,  # type: ignore[call-arg]
                        owner_key=OWNER, profile="EMPLOYEE", hybrid_floor=0.5,
                        lexical_floor=0.3)


@pytest.mark.parametrize("value, error", [(1.2, ValueError), (-0.1, ValueError),
                                          (float("nan"), ValueError), (True, TypeError),
                                          ("0.1", TypeError)])
def test_the_evidence_floor_refuses_a_wiring_slip(value, error):
    with pytest.raises(error):
        access(store(), lexical_evidence_floor=value)
