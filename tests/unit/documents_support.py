"""Shared helpers for the ``consult_documents`` tests — INVENTED data only.

Not a test module (no ``test_`` prefix). Every store here is the REAL
``cogno_engram.InMemoryDocumentStore`` — the reference implementation of the rules the skill
relies on — never a hand-written double: a double would encode what this repo BELIEVES the store
does, and the profile/owner filter is exactly the thing that must not be believed.
"""

from __future__ import annotations

import hashlib
from typing import Optional, Sequence

from cogno_engram.adapters.in_memory import InMemoryDocumentStore
from cogno_engram.documents import COMMIT_READY, MEDIA_MARKDOWN, KbChunk, embed_model_label

from cogno_cortex.skills.consult_documents import DocumentsAccess

DIM = 8
MODEL_A = embed_model_label("stub:alpha", DIM)
MODEL_B = embed_model_label("stub:beta", DIM)
OWNER = "acme/front-desk"


def axis(i: int, weight: float = 1.0) -> list[float]:
    v = [0.0] * DIM
    v[i] = weight
    return v


NEUTRAL = axis(DIM - 1)


def store() -> InMemoryDocumentStore:
    return InMemoryDocumentStore(embedding_dim=DIM)


async def publish(st, owner: str = OWNER, *, title: str = "Student handbook",
                  profiles: Sequence[str] = ("EMPLOYEE",),
                  chunks: Sequence[tuple] = (), model: str = MODEL_A,
                  commit: bool = True) -> str:
    """Publish one document. ``chunks`` are ``(body, heading_trail, page, embedding)``; the
    content is written the way ``cogno_engram.chunking`` writes it — the heading path (which
    starts with the title), a blank line, then the body."""
    doc = await st.create_document(owner, title=title, profiles=list(profiles),
                                   media_type=MEDIA_MARKDOWN)
    raw = repr((title, chunks)).encode()
    v = await st.begin_version(owner, doc.id, sha256=hashlib.sha256(raw).hexdigest(),
                               embed_model=model, size_bytes=len(raw))
    staged = []
    for i, (body, trail, page, emb) in enumerate(chunks):
        path = (title, *trail)
        staged.append(KbChunk(ordinal=i, content=" › ".join(path) + "\n\n" + body,
                              heading_path=path, page=page, embedding=list(emb)))
    assert await st.add_chunks(owner, doc.id, v.version, staged)
    if commit:
        assert await st.commit_version(owner, doc.id, v.version, pages=0) == COMMIT_READY
    return doc.id


class KeyedEmbedder:
    """Deterministic, zero-network: a vector per exact text (``NEUTRAL`` otherwise), and a
    KNOWN token count per call (words + 1) so a test can sum what was reported."""

    def __init__(self, vectors: Optional[dict] = None, *, fail: bool = False,
                 fail_on: Optional[str] = None, width: int = DIM) -> None:
        self.vectors = dict(vectors or {})
        self.fail = fail
        self.fail_on = fail_on
        self.width = width
        self.calls: list[str] = []

    async def embed_with_usage(self, text: str):
        self.calls.append(text)
        if self.fail or (self.fail_on is not None and text == self.fail_on):
            raise ConnectionError("embedder down")
        vec = list(self.vectors.get(text, NEUTRAL))
        vec = (vec + [0.0] * self.width)[:self.width]
        return vec, len(text.split()) + 1


class PlainEmbedder:
    """An embedder WITHOUT usage reporting — only ``embed``."""

    def __init__(self) -> None:
        self.calls = 0

    async def embed(self, text: str) -> list[float]:
        self.calls += 1
        return list(NEUTRAL)


def access(st, embedder=None, **kw) -> DocumentsAccess:
    base = dict(store=st, embedder=embedder or KeyedEmbedder(), embed_model=MODEL_A,
                owner_key=OWNER, profile="EMPLOYEE", hybrid_floor=0.5, lexical_floor=0.3,
                # the evidence gate OFF by default: every test that is not about it keeps the
                # decision it always had (tests/unit/test_consult_documents_lexical_evidence.py)
                lexical_evidence_floor=0.0, records=[])
    base.update(kw)
    return DocumentsAccess(**base)


class SpyStore:
    """The REAL store behind a recorder. ``drop_vector_on`` (a call index, 0-based) makes that
    search go out WITHOUT its vector — the shape of one result coming back lexical while its
    sibling was hybrid (an embedding lost mid-turn, a model swap committing between the two
    searches). ``fail`` makes every search raise."""

    def __init__(self, inner, *, drop_vector_on: Optional[int] = None, fail: bool = False):
        self.inner = inner
        self.embedding_dim = inner.embedding_dim
        self.drop_vector_on = drop_vector_on
        self.fail = fail
        self.searches: list[dict] = []

    async def readable_documents(self, owner_key, *, profile):
        return await self.inner.readable_documents(owner_key, profile=profile)

    async def search(self, owner_key, *, profile, text, vector=None, embed_model=None,
                     limit=5, weights=None):
        index = len(self.searches)
        self.searches.append(dict(owner_key=owner_key, profile=profile, text=text,
                                  vector=vector, embed_model=embed_model, limit=limit))
        if self.fail:
            raise TimeoutError("store unreachable")
        if index == self.drop_vector_on:
            vector, embed_model = None, None
        return await self.inner.search(owner_key, profile=profile, text=text, vector=vector,
                                       embed_model=embed_model, limit=limit, weights=weights)
