# Changelog

## Unreleased

### Added

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
