# Changelog

## Unreleased

### Added — P9: `consult_documents` reads a document WHOLE (needs cogno-engram with `read_served`, #76)

- **Why, measured** (a reference host, 20 labelled questions over the documents it serves): the
  best-3 passages carried the expected content completely in **16/20** («summarise the syllabus»
  got 1 of its 2 blocks, the curriculum grid missing); reading the documents of the shown
  passages whole, **20/20**; the documents served there are small (the largest ~2.1 k tokens).
  The owner's order: «quando a persona tiver documentos, o sistema consiga fazer a leitura
  completa dele».
- **`DocumentsAccess.max_whole_chars`** (default `0` = off), **`whole_doc_chars`** (default `0`)
  and **`section_mode`** (default `False`), validated at construction (a whole budget needs a
  store with `read_served`; `whole_doc_chars` ≤ the budget; a budget ≥ `MIN_ANSWER_CHARS`).
- **Document mode**: for the documents of the passages that PASSED, in the order of their best
  passage, a document with at most `whole_doc_chars` of text is shown as ONE excerpt — section
  headings in line, the chunks' overlap said once (`cogno_engram.chunking.join_passages`) — while
  it fits the budget; the others keep their passages; what fits nowhere is counted.
- **`whole: true`** (optional argument, «when the contact asks for the summary or the complete
  content of a document»): whole whatever the size, up to the budget; a document the budget cuts
  ends with `[continues: document=<id>, after=<ordinal>]`, and **`document` + `after`** read the
  next slice (no search, no embedding). The three arguments are in the schema only when the
  access has a budget (`consult_documents_manifest(..., reading=True)`, passed by
  `offer_consult_documents`).
- **Section mode** — OFF by default: the UNION of the level-2 blocks that hold a long document's
  passages. The block of the best passage alone measured **14/20**, below the passages; the union
  is here to be measured forced, and enters only if it does not lose to them.
- **Every whole read is the store's READER path** (`read_served`, the reader's profile, on every
  call), through ONE seam (`_served_slice`). A forged `document` — another profile's, a draft,
  another owner's, made up — reads nothing: `status="error"`, outcome `unreadable`, the same
  answer for all. `version_text`, the administrator's read, is never used.
- **A negative never expands**: *nothing relevant* returns before any whole read.
- **Off, or nothing expanded → today's payload, byte for byte** (pinned by digest against the
  bytes before this change). A whole read that raises keeps the passages and marks
  `whole_read_unavailable`.
- **`ConsultRecord`** gains `mode` (`passages` | `section` | `document`, closed: `VALID_MODES`),
  `whole_ids`, `continued`, `has_more`, `whole_requested`; outcomes `continued` and
  `unreadable` join `VALID_OUTCOMES`; `shown` counts the passed passages the answer COVERS.
  `hit_ids`, `cut_by` and the scores are as before.
- **Tests** — `tests/unit/test_consult_documents_whole_read.py` (37, invented data):
  - the twin: a small document of the shown passages read whole, every item once (48 + 16);
    control: reading off, the best-3 miss the grid, and chunk by chunk the overlap IS there;
  - byte identity, 3 settings × 5 digests computed before the change;
  - **a negative never expands** (floor cut and evidence cut): no whole read, the legacy
    payload; control: the positive question reads the non-hit section;
  - **another profile, never** — by `whole: true`, by a forged `document`, by a forged
    `profile`; the answer equals a made-up id's; control: the ADMIN reads it by the same call;
  - **a draft, never** — beside the served version and alone; control: `version_text` shows it;
  - a long document: whole on request, cut, continued to its end, every item once;
  - a long one keeps its passages when nobody asks;
  - section mode forced: both blocks, nothing between; control: off by default;
  - the budget: one whole, one in passages;
  - the schema only when reading; the access refusals; a failing read keeps the passages;
  - the arguments coerced, never a crash; without a budget they are ignored;
  - **injection through the WHOLE read** (the #13 review): a document whose text and headings
    carry a `<TOOL_CALL>` and forged `<excerpt …>`/`</excerpt>` fences (upper case and spaced
    too), read in document mode, with `whole: true` and by continuation — no call that parses,
    the fences neutralised, exactly ONE opening and ONE closing fence; control: the served text
    IS hostile. The injection tests before covered the passages only.

  Plus one Postgres test (`tests/integration/test_consult_documents_postgres.py`, CI job
  `integration-postgres`): the whole read and the forged id over the real reader path.
- **Mutations, by hand** (anchor `grep -cxF` = 1, `ast.parse`, red, reverted):
  - the reader seam swapped for the administrator's `version_text` →
    `test_TWIN_another_profiles_document_never_appears_not_even_by_a_forged_document_id`;
  - the evidence gate dropped (`passed = cleared[:limit]`) →
    `test_TWIN_a_nothing_relevant_reading_never_reads_a_document[…lexical_evidence]`;
  - the section union reduced to the first passage (`for hit in hits[:1]:`) →
    `test_section_mode_forced_reads_the_union_of_the_blocks_that_hold_the_passages`;
  - the overlap not removed (`_document_body(g, …)`) →
    `test_TWIN_a_small_document_of_the_shown_passages_is_read_whole_every_item_said_once`.
  - the whole path's text not sanitised (`text = _defang(…)` → the raw text) →
    `test_TWIN_a_hostile_document_read_WHOLE_can_neither_plant_a_call_nor_break_the_fence`
    (its three cases, nothing else);
  - The draft rule is the store's (`read_served`), and its mutation is in cogno-engram #76.

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

- **`describe_documents(..., sections=None)`: the SECTIONS under each title in the
  `consult_documents` description (P9.0).** The executor chooses a tool by its description, and
  the description listed TITLES only. Measured on a reference host (n=3 per arm), a request about
  a subject that lived only in a SECTION of a document:
  - **titles only:** `consult_documents` was chosen **0/3**; the other tool was chosen 3/3;
  - **sections listed:** `consult_documents` was chosen **3/3**;
  - the control, a request that belonged to the other tool, went to that tool 3/3 in both arms.
  - `sections` maps a document's **id** to its headings (by id, not by title: two documents may
    share a title, and a caller's cleaned title need not equal the raw one). Anything but a
    mapping (a list, a string, a number) is no sections at all, never an error. Each heading goes
    through the SAME `_label` as a title (whitespace collapsed, `sanitize_untrusted`,
    excerpt-fence tags defanged) and is written under the titles as one `"Title › Section"` JSON
    literal per line.
  - Ceilings in a scope guard's UNIT (the reference host's facts block, the same numbers):
    - `MAX_SECTION_CHARS` = 60 per section;
    - `MAX_SECTIONS_PER_DOCUMENT` = 12;
    - `MAX_SECTIONS_CHARS` = 1200 characters of section TEXT in all (the headings, not the
      rendered lines), where the first section that does not fit ends its document's list.

    The rest are COUNTED (`(and N more sections)`), including the sections of a document past the
    title ceiling. A host that hands over the sections its guard rendered can never have them cut
    differently here, so the executor never sees a section the guard did not.
  - **No section to write → today's bytes**, pinned by SHA-256 against four inputs whose digests
    were computed on `main` b3ca3bb before this change, under nine "no section" shapes (five
    mappings with nothing usable, and a list, a pair list, a string and a number).
  - **Personal data is the caller's filter**: a heading comes from the file's CONTENT and was
    never checked, and this module cannot tell a name from a word. `offer_consult_documents`
    therefore passes **no** sections; a host hands over only the headings it filtered.
  - Tests: `tests/unit/test_consult_documents_sections.py` covers:
    - the twin: sections under their titles; control: without them, none;
    - byte identity (control: one real section moves the digest);
    - a planted call, an excerpt fence, a quote and a line break in a section, all defanged;
    - a long section cut to 60;
    - the per-document ceiling counted;
    - the character twin: 3 × 12 sections of 60 characters give exactly 1200 characters of text
      listed, 16 counted; control: the rendered lines are longer than 1200, so the unit is the
      text;
    - `offer_consult_documents` never putting the store's headings in the description (control:
      the store does return them).
  - **Mutations, by hand** (anchor `grep -cxF` = 1, `ast.parse`, red, reverted):
    - the sections never rendered (`if isinstance(sections, Mapping) else ([], 0)` →
      `if False else ([], 0)`) → `test_twin_the_description_lists_each_section_under_its_title`
      red, with the four other section tests and the control half of all 36 byte-identity cases
      (41 failed, 1 passed);
    - the character budget switched off (`if len(label) > budget:` → `if False:`) →
      `test_TWIN_the_total_ceiling_is_in_CHARACTERS_of_section_text_the_guards_unit` red.

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
