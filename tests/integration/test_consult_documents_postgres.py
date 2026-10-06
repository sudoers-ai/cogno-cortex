"""``consult_documents`` over the REAL ``PostgresDocumentStore`` — what the in-memory store
cannot show: the scale the floors are calibrated on (``ts_rank_cd`` with normalisation 32 and
pgvector's cosine), the ``portuguese`` stemmer with ``unaccent`` (a question typed without
accents must find the passage that has them), and the profile/owner filter as SQL.

**Where it runs.** Only against a database named in ``CORTEX_TEST_PG_DSN`` — never an ambient
DSN, never a default server — and only when that database's NAME says ``test``: this module
DROPs and recreates the ``kb_*`` tables. A DSN that names anything else FAILS the run instead of
skipping it, because a skip would hide that somebody aimed a destructive suite at a real
database. No DSN → skip (the CI job ``integration-postgres`` sets it). No model, no GPU: the
embedder is a deterministic double.
"""

from __future__ import annotations

import hashlib
import os
from urllib.parse import urlsplit
from uuid import uuid4

import pytest

from cogno_engram.documents import (
    COMMIT_READY,
    KB_EMBED_SPACE_UNAVAILABLE,
    MEDIA_MARKDOWN,
    KbChunk,
    embed_model_label,
)

from cogno_cortex import ToolContext
from cogno_cortex.skills.consult_documents import (
    CUT_LEXICAL_EVIDENCE,
    META_DOCUMENTS_ACCESS,
    OUTCOME_HITS,
    OUTCOME_NOTHING_RELEVANT,
    VARIANT_USER,
    ConsultDocumentsTool,
    DocumentsAccess,
    offer_consult_documents,
)

DIM = 8
MODEL_A = embed_model_label("stub:alpha", DIM)
MODEL_B = embed_model_label("stub:beta", DIM)
KB_TABLES = ("kb_chunks", "kb_originals", "kb_versions", "kb_tombstones", "kb_documents")
DERIVED = ("cogno_portuguese_unaccent",)
DSN = (os.environ.get("CORTEX_TEST_PG_DSN") or "").strip()


def _axis(i: int) -> list[float]:
    v = [0.0] * DIM
    v[i] = 1.0
    return v


NEUTRAL = _axis(DIM - 1)


class _Embedder:
    """Deterministic: a vector per text (``NEUTRAL`` otherwise), words + 1 tokens per call."""

    def __init__(self, vectors=None) -> None:
        self.vectors = dict(vectors or {})
        self.calls: list[str] = []

    async def embed_with_usage(self, text: str):
        self.calls.append(text)
        return list(self.vectors.get(text, NEUTRAL)), len(text.split()) + 1


@pytest.fixture
async def pg():
    if not DSN:
        pytest.skip("CORTEX_TEST_PG_DSN is not set — the in-memory unit suite ran instead")
    name = urlsplit(DSN).path.lstrip("/").lower()
    if "test" not in name:
        pytest.fail(f"refusing to DROP kb_* tables in database {name!r}: its name must say 'test'")
    psycopg = pytest.importorskip("psycopg")
    from cogno_engram.adapters.postgres import PostgresDocumentStore, ensure_documents_schema
    try:
        conn = await psycopg.AsyncConnection.connect(DSN, autocommit=True, connect_timeout=3)
    except Exception as exc:                                   # noqa: BLE001
        pytest.skip(f"test Postgres unreachable: {type(exc).__name__}")
    try:
        for table in KB_TABLES:
            await conn.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
        for derived in DERIVED:
            await conn.execute(f"DROP TEXT SEARCH CONFIGURATION IF EXISTS {derived}")
        await ensure_documents_schema(conn, embedding_dim=DIM, ts_config="portuguese",
                                      unaccent=True)
    finally:
        await conn.close()
    st = PostgresDocumentStore(dsn=DSN, embedding_dim=DIM, ts_config="portuguese", unaccent=True)
    yield st
    close = getattr(st, "close", None)
    if close is not None:
        await close()


async def _publish(st, owner, *, title, profiles, chunks, model=MODEL_A) -> str:
    doc = await st.create_document(owner, title=title, profiles=list(profiles),
                                   media_type=MEDIA_MARKDOWN)
    raw = repr((title, chunks)).encode()
    v = await st.begin_version(owner, doc.id, sha256=hashlib.sha256(raw).hexdigest(),
                               embed_model=model, size_bytes=len(raw))
    staged = [KbChunk(ordinal=i, content=" › ".join((title, *trail)) + "\n\n" + body,
                      heading_path=(title, *trail), page=page, embedding=list(emb))
              for i, (body, trail, page, emb) in enumerate(chunks)]
    assert await st.add_chunks(owner, doc.id, v.version, staged)
    assert await st.commit_version(owner, doc.id, v.version, pages=1) == COMMIT_READY
    return doc.id


def _access(st, owner, **kw) -> DocumentsAccess:
    base = dict(store=st, embedder=_Embedder(), embed_model=MODEL_A, owner_key=owner,
                profile="EMPLOYEE", hybrid_floor=0.3, lexical_floor=0.05,
                lexical_evidence_floor=0.0, records=[])
    base.update(kw)
    return DocumentsAccess(**base)


async def _run(acc, query):
    return await ConsultDocumentsTool(query=query).run(
        ToolContext(metadata={META_DOCUMENTS_ACCESS: acc}))


SAT = ("Aos sábados abrimos das 8h às 12h.", ("Horários", "Sábado"), 3, NEUTRAL)


async def test_profile_and_owner_are_filtered_by_the_store_itself(pg):
    owner = f"acme{uuid4().hex[:6]}/front-desk"
    await _publish(pg, owner, title="Manual interno", profiles=("EMPLOYEE",), chunks=[SAT])
    staff = _access(pg, owner)
    res = await _run(staff, "sábado")
    assert staff.records[0].outcome == OUTCOME_HITS and "abrimos das 8h" in res.payload  # CONTROL

    for acc in (_access(pg, owner, profile="GUEST"),
                _access(pg, owner.split("/")[0]),                 # the parent key is not the owner
                _access(pg, owner + "2")):
        res = await _run(acc, "sábado")
        assert "abrimos" not in res.payload
        assert acc.records[0].outcome == OUTCOME_NOTHING_RELEVANT

    assert await offer_consult_documents(_access(pg, owner, profile="GUEST")) is None
    offered = await offer_consult_documents(staff)
    assert offered is not None and '"Manual interno"' in offered.description


async def test_a_question_without_accents_finds_the_passage_that_has_them(pg):
    owner = f"acme{uuid4().hex[:6]}/front-desk"
    await _publish(pg, owner, title="Manual", profiles=("GUEST",),
                   chunks=[SAT, ("Estacionamento gratuito.", ("Estacionamento",), 4, _axis(0))])
    acc = _access(pg, owner, profile="GUEST", embed_model=MODEL_B, user_text="e no sabado?")
    # MODEL_B labels the question; every passage was indexed by MODEL_A → the store scores by
    # WORDS only and says so, so what is measured here is the lexical path alone.
    res = await _run(acc, "saturday opening hours")
    rec = acc.records[0]
    assert KB_EMBED_SPACE_UNAVAILABLE in rec.degradations and rec.lexical
    assert rec.floor == acc.lexical_floor
    assert rec.outcome == OUTCOME_HITS and "abrimos das 8h" in res.payload
    assert rec.hit_variants[0] == VARIANT_USER          # the English query shares no Portuguese word
    assert all(0.0 < s <= 1.0 for s in rec.scores)
    assert "Estacionamento gratuito" not in res.payload


async def test_the_hybrid_scale_is_what_postgres_returns(pg):
    owner = f"acme{uuid4().hex[:6]}/front-desk"
    await _publish(pg, owner, title="Manual", profiles=("EMPLOYEE",),
                   chunks=[SAT, ("Estacionamento gratuito.", ("Estacionamento",), 4, _axis(0))])
    acc = _access(pg, owner, hybrid_floor=0.5)
    res = await _run(acc, "sábado")
    rec = acc.records[0]
    assert not rec.lexical and rec.degradations == () and rec.floor == 0.5
    # The Saturday passage: vector 1.0 (same axis), words > 0 → above 0.6; the parking one:
    # vector 0, no shared word → 0.0, below the floor and counted.
    assert len(rec.scores) == 1 and rec.scores[0] > 0.6
    assert rec.below_floor == 1
    assert "Sábado · page 3" in res.payload


# ── the lexical-EVIDENCE gate on the production scale (``ts_rank_cd`` + ``portuguese`` +
# ``unaccent``): the index's own fold decides what counts as a shared word ─────────────────

async def test_evidence_is_the_same_for_sabado_and_Sabado_under_the_index_fold(pg):
    owner = f"acme{uuid4().hex[:6]}/front-desk"
    await _publish(pg, owner, title="Manual", profiles=("EMPLOYEE",), chunks=[SAT])
    got = {}
    for typed in ("sábado", "sabado", "SÁBADO"):
        acc = _access(pg, owner, lexical_evidence_floor=0.01)
        await _run(acc, typed)
        rec = acc.records[0]
        assert rec.outcome == OUTCOME_HITS and not rec.lexical, (typed, rec)
        got[typed] = rec.lexical_evidence
    assert len(set(got.values())) == 1 and next(iter(got.values())) > 0.0, got


async def test_PRICE_on_postgres_a_paraphrase_with_no_common_word_is_cut(pg):
    owner = f"acme{uuid4().hex[:6]}/front-desk"
    await _publish(pg, owner, title="Manual", profiles=("EMPLOYEE",), chunks=[SAT])
    q = "funcionamento no fim de semana"  # the same topic (the same vector), no common lexeme
    off = _access(pg, owner, hybrid_floor=0.5)
    res = await _run(off, q)
    assert off.records[0].outcome == OUTCOME_HITS and "abrimos das 8h" in res.payload  # CONTROL
    assert off.records[0].lexical_scores == (0.0,)
    on = _access(pg, owner, hybrid_floor=0.5, lexical_evidence_floor=0.05)
    res = await _run(on, q)
    rec = on.records[0]
    assert rec.outcome == OUTCOME_NOTHING_RELEVANT and "abrimos" not in res.payload
    assert rec.cut_by == CUT_LEXICAL_EVIDENCE and rec.lexical_evidence == 0.0


async def test_WHOLE_on_postgres_the_served_document_whole_and_a_forged_id_reads_nothing(pg):
    """P9 over the REAL reader path: ``read_served`` as SQL (the one ``_SERVED`` filter) reads
    the document of the shown passage whole — a section no passage matched included — and a
    forged ``document`` of another profile reads nothing (its CONTROL: the profile it is published
    to reads it by the same call)."""
    from cogno_cortex.skills.consult_documents import (MODE_DOCUMENT, OUTCOME_CONTINUED,
                                                       OUTCOME_UNREADABLE)
    owner = f"acme{uuid4().hex[:6]}/front-desk"
    manual = await _publish(pg, owner, title="Manual interno", profiles=("EMPLOYEE",), chunks=[
        SAT, ("Taxa de inscrição: NONHIT-MARCA-7.", ("Preços",), 3, NEUTRAL)])
    staff_only = await _publish(pg, owner, title="Notas da direção", profiles=("ADMIN",),
                                chunks=[("Orçamento ZETA-ADMIN-MARCA.", ("Notas",), 1, NEUTRAL)])
    whole = dict(whole_doc_chars=12000, max_whole_chars=24000)
    staff = _access(pg, owner, **whole)
    res = await _run(staff, "sábado")
    assert staff.records[-1].mode == MODE_DOCUMENT and staff.records[-1].whole_ids == (manual,)
    assert "NONHIT-MARCA-7" in res.payload and "abrimos das 8h" in res.payload
    forged = await ConsultDocumentsTool(query="x", document=staff_only).run(
        ToolContext(metadata={META_DOCUMENTS_ACCESS: staff}))
    assert forged.status == "error" and "ZETA-ADMIN" not in (forged.payload or "")
    assert staff.records[-1].outcome == OUTCOME_UNREADABLE
    admin = _access(pg, owner, profile="ADMIN", **whole)
    ok = await ConsultDocumentsTool(query="x", document=staff_only).run(
        ToolContext(metadata={META_DOCUMENTS_ACCESS: admin}))
    assert "ZETA-ADMIN-MARCA" in ok.payload and admin.records[-1].outcome == OUTCOME_CONTINUED


# ── the floor's one exception on the production scale: evidence by the section HEADING ────
#
# The FORM of the measured case, INVENTED data: a section that is a table (years and figures,
# little prose) under a numbered heading of several words. Its vector is weak (``v = 0.25``) and
# ``ts_rank_cd`` of a table is low, so its fused score is under the floor even though it is the
# answer. The heading test itself is client-side (the engram's word rule); what this leg adds is
# the REAL scale the fused score is on.

QUARTER = [0.0, 0.0, 0.0, 15.0 ** 0.5, 0.0, 0.0, 0.0, 1.0]     # cos 0.25 against NEUTRAL
RATES = ("| Ano | Diária média |\n|---|---|\n| 2019 | R$ 210 |\n| 2021 | R$ 185 |\n"
         "| 2023 | R$ 240 |", ("12. Variação das Diárias",), 7, QUARTER)
ACCESS = ("A pousada fica a 2 km do centro, com acesso por estrada asfaltada.",
          ("3. Localização e Acesso",), 2, _axis(1))


async def test_HEADING_on_postgres_a_table_section_under_the_floor_passes_by_its_heading(pg):
    owner = f"acme{uuid4().hex[:6]}/front-desk"
    doc = await _publish(pg, owner, title="Relatório anual da Pousada Vento Norte",
                         profiles=("EMPLOYEE",), chunks=[ACCESS, RATES])
    asked = "Como foi a variação das diárias?"
    # the host's numbers: a hybrid floor of 0.40 and an evidence floor of 0.13
    acc = _access(pg, owner, hybrid_floor=0.4, lexical_evidence_floor=0.13, user_text=asked)
    res = await _run(acc, "variação das diárias ao longo dos anos")
    rec = acc.records[0]
    assert not rec.lexical and rec.outcome == OUTCOME_HITS, rec
    assert rec.hit_ids == (f"kb:{doc}.1.1",) and rec.heading_match == 1
    assert rec.scores[0] < 0.4, "under the floor on the real scale — it passed by its heading"
    assert rec.lexical_evidence is not None and rec.lexical_evidence >= 0.13, "and the 2nd gate"
    assert rec.below_floor >= 1 and "| 2021 | R$ 185 |" in res.payload
    # the CONTROL on the same store: a question that shares ONE word of the heading is judged by
    # the floor, as before
    one = _access(pg, owner, hybrid_floor=0.4, lexical_evidence_floor=0.13,
                  user_text="Como foi a variação do câmbio?")
    await _run(one, "Como foi a variação do câmbio?")
    assert one.records[0].outcome == OUTCOME_NOTHING_RELEVANT and one.records[0].cut_by == "floor"
    assert one.records[0].heading_match == 0 and one.records[0].below_floor >= 1


# ── the heading test, the INVERSE direction, on the production scale ─────────────────────
#
# The FORM of the second measured case, INVENTED data: the executor's query is ONE word, the
# subject's name, and two sections carry it in their heading next to a word the question does
# not («9. Quintarelo — Investimento»). Only the inverse direction can match there.
#
# A PREDICTION this leg measures, written before it ran: ``kb_chunks.tsv`` has no weights, so a
# one-word query that occurs ONCE in a chunk (the heading line the content starts with) has
# ``ts_rank_cd = 0.1`` and, under normalisation 32 (``r / (r + 1)``), a lexical score of 0.091 —
# under the host's evidence floor of 0.13. Twice → 0.2 → 0.167, over it. So a section whose body
# names its subject again is read; a TABLE that names it only in its heading is rescued by the
# floor's exception and then cut by the evidence gate, as the direct direction would be. The
# gate is deliberately unchanged here.

INVESTMENT = ("| Ano | Aporte |\n|---|---|\n| 2019 | R$ 480.000 |\n| 2022 | R$ 95.000 |",
              ("9. Quintarelo — Investimento",), 4, QUARTER)
RENT = ("O Quintarelo rendeu em aluguel:\n\n| Ano | Valor |\n|---|---|\n| 2023 | R$ 62.400 |\n"
        "| 2024 | R$ 66.000 |", ("10. Quintarelo — Receita de Aluguel",), 5, QUARTER)
INVEST_NAMED = ("O Quintarelo recebeu estes aportes:\n\n" + INVESTMENT[0], INVESTMENT[1], 4,
                QUARTER)
HOUSE = ("A rede da casa principal chama-se Casa-Norte; a senha fica com o caseiro.",
         ("4. Casa Principal — Serviços",), 3, QUARTER)
ESTATE = "Relatório patrimonial da Família Brandomar"


async def test_HEADING_INVERSE_on_postgres_a_one_word_question_reads_the_sections_it_heads(pg):
    owner = f"acme{uuid4().hex[:6]}/front-desk"
    doc = await _publish(pg, owner, title=ESTATE, profiles=("EMPLOYEE",),
                         chunks=[HOUSE, INVEST_NAMED, RENT])
    acc = _access(pg, owner, hybrid_floor=0.4, lexical_evidence_floor=0.13,
                  user_text="O que sabe sobre o Quintarelo?")
    res = await _run(acc, "Quintarelo")
    rec = acc.records[0]
    assert not rec.lexical and rec.outcome == OUTCOME_HITS, rec
    assert {f"kb:{doc}.1.1", f"kb:{doc}.1.2"} <= set(rec.hit_ids), rec
    assert rec.heading_match == sum(1 for s in rec.scores if s < 0.4), rec
    assert "| 2022 | R$ 95.000 |" in res.payload and "| 2024 | R$ 66.000 |" in res.payload
    # the CONTROL on the same store: the Wi-Fi password names no heading
    wifi = _access(pg, owner, hybrid_floor=0.4, lexical_evidence_floor=0.13,
                   user_text="Qual a senha do Wi-Fi?")
    await _run(wifi, "Qual a senha do Wi-Fi?")
    assert wifi.records[0].heading_match == 0, wifi.records[0]
    assert not {f"kb:{doc}.1.1", f"kb:{doc}.1.2"} & set(wifi.records[0].hit_ids)


async def test_HEADING_INVERSE_on_postgres_a_table_named_only_in_its_heading_meets_the_gate(pg):
    owner = f"acme{uuid4().hex[:6]}/front-desk"
    doc = await _publish(pg, owner, title=ESTATE, profiles=("EMPLOYEE",),
                         chunks=[HOUSE, INVESTMENT])
    acc = _access(pg, owner, hybrid_floor=0.4, lexical_evidence_floor=0.13, user_text="Quintarelo")
    await _run(acc, "Quintarelo")
    rec = acc.records[0]
    assert rec.heading_match == 1, rec
    assert rec.lexical_evidence is not None and rec.lexical_evidence < 0.13, rec
    assert rec.outcome == OUTCOME_NOTHING_RELEVANT and rec.cut_by == CUT_LEXICAL_EVIDENCE, rec
    # the presence: the same store with the evidence gate off reads the table
    off = _access(pg, owner, hybrid_floor=0.4, lexical_evidence_floor=0.0, user_text="Quintarelo")
    await _run(off, "Quintarelo")
    assert off.records[0].outcome == OUTCOME_HITS and off.records[0].hit_ids == (f"kb:{doc}.1.1",)
