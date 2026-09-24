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
                profile="EMPLOYEE", hybrid_floor=0.3, lexical_floor=0.05, records=[])
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
