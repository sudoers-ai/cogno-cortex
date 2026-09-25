# Changelog

## Unreleased

### Changed (docs)

- **Phase 2 docs sweep B — `consult_documents` after the evidence gate (#10).**
  `ConsultRecord`'s docstring said `variants` are "the texts searched"; the code stores their
  LABELS (`user` / `model`, `tests/unit/test_consult_documents.py`), never the texts. It now says
  so, and names what it did not: `below_floor`, the evidence gate among what makes a passage
  "pass", and the `limit` cap. `docs/HOST_INTEGRATION.md` §7 listed "the two floors" to wire —
  `lexical_evidence_floor` is required since #10 — and now names the three and `cut_by`.
  `docs/CONSULT_DOCUMENTS.md` § *What it spends* adds `below_floor` and `shown` and says the
  variants are labels. Docs and a docstring only; no behaviour changes.

### Added

- **`consult_documents`: a second gate in HYBRID mode, on lexical EVIDENCE.** Among the passages
  that clear the hybrid floor, at least one must share the question's words (its store-side
  `lexical_score` ≥ `DocumentsAccess.lexical_evidence_floor`), or the reading is *nothing
  relevant*. `lexical_evidence_floor` is **required** with no default, like the two floors (`0`
  switches the gate off). The gate reads the SET that cleared the floor, never only its first
  passage; it only decides — what is shown, and in which order, is unchanged; it does not apply
  to a lexical result; and the word test is the store's own, under the index's fold (*Sábado* =
  *sabado*). `ConsultRecord` gains `cut_by` (`floor` | `lexical_evidence`, closed:
  `VALID_CUTS`), `lexical_evidence` and `lexical_scores` (parallel to `scores`). **Breaking** for
  a caller that builds `DocumentsAccess`: the new field is required.
  **Risk, declared:** a passage that answers purely by paraphrase — no word in common with
  either text searched — is now *nothing relevant*; `test_PRICE_*` produce that loss on purpose
  (in memory and on Postgres). Why a gate and not a higher floor: a topic-only match can carry an
  unanswerable question over the fused floor, and on a reference host the zero-loss floor of one
  corpus cut real answers in another.

- **`cogno_cortex.skills.consult_documents`** — the first GENERIC skill shipped with the framework
  (extra `documents`, which pulls `cogno-engram`): searches a `cogno_engram.DocumentStore` on
  demand and returns passages with provenance (`id · document › section · page`), or says plainly
  that nothing in the documents is relevant. Business-free by construction: the store, the
  embedder, the owner key and the reader's profile arrive injected in ONE `DocumentsAccess`
  (metadata key `documents_access`); the model fills only `query`, and a `profile`/`owner_key` it
  invents is dropped. Two searches — the contact's own words and the model's query — fused by the
  MAXIMUM per passage; the floor is a parameter with TWO required values (hybrid / lexical), chosen
  by the store's `kb_embed_space_unavailable` mark or by a failed embedding, and the two searches
  are always on one scale. An embedder failure degrades to words and never fails the turn; a store
  failure is an error that says not to read it as an absence. `describe_documents` (pure) builds
  the tool description from the readable titles, sanitised; `offer_consult_documents` returns
  `None` when the reader has nothing readable. One content-free `ConsultRecord` per execute is
  appended to a list the host pre-placed — the channel for the query-embedding usage, because
  `CortexDispatcher` carries only the result text to `ToolResult`. See
  `docs/CONSULT_DOCUMENTS.md`.
- CI: the unit job installs `cogno-engram[postgres]` from git; a new `integration-postgres` job
  runs the skill against the real `PostgresDocumentStore` (pgvector service), so that leg runs in
  public instead of skipping.

### Fixed (docs)

- `docs/HOST_INTEGRATION.md` said `SkillResult.usage` could be fed to the meter; through
  `CortexDispatcher` it never reaches the host (`ToolResult` has no usage field). Now said, with
  the pre-placed-sink pattern as the way a skill hands usage back.

## 0.1.0 — 2026-07-25

First public release on PyPI.

The in-process skills framework for the Cogno stack — author skills as BaseTool + manifest, rank them against NER tags, execute via a provider bus, discover from disk, and bridge to cogno-anima's tool contract via CortexDispatcher. The framework, not the skills; infra-agnostic.
