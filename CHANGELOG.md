# Changelog

## Unreleased — the heading test, the INVERSE direction: the question's subject IN the heading

### Changed

- **A short question that names its subject now reads the sections that subject heads.**
  Measured on a reference host: the EGO's query was ONE word, the subject's name; the store
  returned three passages, all under the hybrid floor of 0.40 (`cut_by=floor`,
  `nothing_relevant`), from a document whose sections «9. *Subject* — Investment» and
  «10. *Subject* — Rental income» held the answer. The heading test needed EVERY content word of
  the heading in the question (and ≥ 2 of them), which a one-word question never meets. Now
  `_heading_matches` also accepts the other direction: EVERY subject word of ONE text searched is
  in the heading, and that text has at least one.
  - **subject word** = a content word (`cogno_engram.lexical.terms`, as before) that is not
    digits-only and not a business's frame word. The frame words are NOT a new list: they are
    `cogno_anima.stages.scope_options.GENERIC_SUBJECT_WORDS`, compared as there (cut to
    `EVIDENCE_PREFIX` = 6), imported — so a word added there is generic here the same day;
  - the record: `heading_match` counts the passages rescued, either direction (no new field —
    every record keeps its old shape);
  - one existing test changed its INPUT, not its claim:
    `test_the_words_must_be_in_ONE_text_not_spread_over_the_two` asked «Como foi a variação?»,
    whose one subject word IS in the heading «Variação das Diárias» — the inverse rescues it,
    rightly. It now asks «Como foi a variação no inverno?», so it still tests what it is named
    for (the heading's words split over the two texts).

### Declared limit

A frame VERB the shared list does not carry is a subject word: «O que sabe sobre o *X*?» keeps
«sabe» («saber» is listed; at 6 characters «sabe» ≠ «saber»), so the contact's sentence ALONE is
not rescued. The measured shape is — the model's query is the bare subject. The conjugations
belong in the anima's list (a follow-up there, not a second list here);
`test_LIMIT_the_literal_sentence_with_sabe_is_not_rescued_by_itself` fails the day they land.

### Unchanged

Everything the direct direction already did: only in hybrid mode, only into slots the floor left
empty, after everything that cleared it, still facing the evidence gate; a lexical result is
untouched. The four byte-identity digests against `main` (d42aa6c) still hold.

### On the production scale (`tests/integration/test_consult_documents_postgres.py`)

A PREDICTION, written before the Postgres leg ran it: `kb_chunks.tsv` carries no weights, so a
one-word query that occurs ONCE in a chunk (only in the heading line) scores `ts_rank_cd` 0.1 →
0.091 under normalisation 32, below the host's evidence floor of 0.13; twice → 0.167, over it. A
section whose body names its subject again is read; a TABLE named only in its heading is rescued
by the floor's exception and then cut by the evidence gate (`cut_by=lexical_evidence`,
`heading_match=1`) — the gate is deliberately unchanged. Both are pinned there.

### Tests (`tests/unit/test_consult_documents_heading_inverse.py`, invented data only)

- **twin:** a one-word question reads the two sections its subject heads (`heading_match=2`); on
  `main` the same store reads `nothing_relevant`, `cut_by=floor`, `below_floor=3`. Also: the
  contact's sentence + the model's bare-subject query; case, punctuation, digits; a two-word
  subject inside ONE heading.
- **controls:** a frame-word question («Escola?», «escolas», «Documentos?», «E a empresa?»)
  lifts none of three sections headed by it — with the frame words switched off the same
  question lifts all three (the presence); a question of stopwords only; the Wi-Fi password (3
  forms) reads nothing though the store returned passages; a word only in a body or the document
  title; one subject word missing from the heading; the slots the floor left.
- **mutations** (each with its anchor counted and the result `ast.parse`d): without the ≥ 1
  condition → 6 tests red (the generic controls, the stopwords control, the twin's broken-world
  half); without the frame words → the 4 generic controls red; without the inverse → 12 red (the
  twins, the fold, the two-word subject, the slots, and the generic controls' presence).

## Unreleased — C4: evidence by the section HEADING, the hybrid floor's one exception

### Added

- **A passage below the HYBRID floor passes when its section heading names the question.**
  Measured on a reference host: a section that IS a table (years and figures, little prose)
  came back FIRST with a fused score of 0.361 under a hybrid floor of 0.40 (vector 0.490,
  lexical 0.167), and the same 0.361 with the section's exact heading as the query; the record
  said `cut_by=floor`, `below_floor=3`, and the contact was told the documents did not say.
  - **names** = EVERY content word of the heading (the leaf of `heading_path`; the document title
    is never the section) is in ONE of the texts searched — the model's `query` or the contact's
    words, not spread over the two — and the heading has at least `MIN_HEADING_WORDS` (2) of
    them;
  - **the words** are `cogno_engram.lexical.terms` — the engram's one tokenizer and stopword list
    over `cogno_engram.textfold.fold`, the fold the in-memory index uses and the one this module
    already compared its two variants with. A digits-only token (the outline's `12.`, a table's
    years) is not a content word. The Postgres index's `portuguese` + `unaccent` fold lives in SQL
    and has no client-side twin, so the heading test is the engram's word rule, on both sides;
  - **why a floor of 2 words, not a list of generic headings**: one shared word is what the rule
    refuses everywhere else, so a one-word heading would be that same word under another name,
    and a list of generic words is per language and fails OPEN on the one it forgot. Measured,
    not argued: with the floor at 1 word an EXISTING test of the evidence gate goes red
    (`test_a_word_only_BELOW_the_floor_is_not_evidence`, where a passage headed «Parking» below
    the floor must not be evidence for «weekend parking») — a closed list would not list
    «Parking» and would break it the same way. The price: a SPECIFIC one-word heading does not
    get the exception either, and is judged by the floor as before.
- **`ConsultRecord.heading_match`** (int, `0` by default): how many passages passed by heading.
  `below_floor` still counts every passage that scored under the floor, so the floor cut
  `below_floor - heading_match`. The evidence line gains `heading_match=N` only when `N > 0`.
- **`MIN_HEADING_WORDS`** exported.

### Unchanged

- the floor for every other passage; a rescued passage only fills a slot the floor left empty
  (so it is always SHOWN) and sits after everything that cleared the floor — the score's order;
- it still faces the evidence gate (a heading's passage with too little lexical evidence is cut
  by `lexical_evidence`, with `heading_match` saying it got that far);
- a LEXICAL result: its floor already is a words test, and the exception was measured on the
  hybrid scale only;
- with nothing rescued, the record (every old field), the payload and the evidence are the old
  ones **byte for byte** — four worlds pinned by digest against `main` (d42aa6c), and `cut_by`
  is `floor` exactly when it was.

### Its price

A question that repeats a section's heading word for word lifts that section from under the
floor even when the section does not hold the answer; it is shown with its provenance.

### Tests (`tests/unit/test_consult_documents_heading_evidence.py`, invented data only)

- **the twin** — the FORM of the measured case: a table section («12. Variação das Diárias», an
  invented inn, invented years and figures), the right passage FIRST at 0.35 under a 0.40 floor,
  → passes with `heading_match=1`; either text alone names it; case, accents, spacing and the
  plural fold (3 spellings). **In the broken world** (`main`, the same file) the twin and those
  four fail on their FIRST assertion: `outcome == 'nothing_relevant'`, `cut_by='floor'`.
- **controls:** ONE word of a heading of several does not pass (2 questions); a one-word
  heading does not pass («Geral», «Outros», and the price, «Estacionamento»), each with its
  presence produced at a floor of 1 word; four worlds the exception does not touch reproduce
  `main` by digest (three clear the floor with a named heading below and no free slot; the
  heading's passage clears on its own; no heading named; nothing relevant by the floor), with a
  test that reads each world for the shape it claims; the rescued passage is APPENDED after what
  cleared the floor, against the same world with the exception off; a lexical result, the
  document title, the words spread over the two texts, the evidence gate, the slot cap.
- **SHAPES of the P9 ruler's controls — invented, not its data:** four negative shapes (one
  heading word shared; the document title's words; a heading split over the two texts; a
  generic word alone) stay *nothing relevant* by the floor; three positive shapes keep every
  passage that cleared the floor, in order, with the same scores.
- **Mutations, through the gate** (anchor count 1, `ast.parse`, red, `reset --hard`):
  - **ALL → ANY** heading word (the mandatory one) → both one-word controls, the two-texts test
    and 2 negative shapes (5 failed / 233 passed);
  - digits count as content words → the twin and every test that needs the heading to match (12
    failed);
  - a floor of 1 word → the three one-word controls, the constant, and the existing
    `test_a_word_only_BELOW_the_floor_is_not_evidence` (5 failed);
  - the exception on the lexical scale too → the lexical test (1 failed);
  - the union of the two texts → the two-texts test and its negative shape (2 failed);
  - no slot cap → the slot test (1 failed);
  - the document title counted as a section → the title test (1 failed).
- **The Postgres leg** (`tests/integration/test_consult_documents_postgres.py`, the CI job
  `integration-postgres`): the twin on the REAL scale (`ts_rank_cd` + `portuguese` + `unaccent`,
  pgvector), with the host's numbers — fused 0.242 under a 0.40 floor, lexical 0.231 over a 0.13
  evidence floor → passes with `heading_match=1`; on `main` the same test reads
  `nothing_relevant`, `cut_by=floor`. Its control on the same store (one heading word shared)
  stays `nothing_relevant` by the floor.
- **The P9 ruler** (24 labelled questions over a reference host's documents) was NOT run for
  this entry: it reads a live store and embeds with a local model. It is run before landing by
  whoever owns that instrument.

## Unreleased — P9.0-b: the sections grouped BY DOCUMENT — each title once, the ceiling on what is rendered

### Changed

- **`describe_documents(..., sections=…)` writes ONE line per document**: `"Title": "Section";
  "Other section"` — the title once, its sections beside it. The first form (P9.0, #12) wrote one
  line per SECTION, each repeating its title.
- **`MAX_SECTIONS_CHARS` (1200) now counts the section block AS RENDERED** — titles, quotes,
  separators and line breaks, i.e. what the executor is sent — instead of the headings' text. A
  section is written while its document's line, with it, still fits what is left; the first that
  does not fit ends that line (the guard's rule, in the rendered unit). `MAX_SECTION_CHARS` (60)
  and `MAX_SECTIONS_PER_DOCUMENT` (12) are unchanged. The rest are counted, as before.
- Every number is at most the reference guard's, so a host handing over the sections its guard
  rendered can only see FEWER here — never one the guard did not (executor ⊆ guard still holds;
  equality no longer does when the block is full).
- **With no section to write, today's bytes**: the digests pinned in #12 hold unchanged.
- **Measured** (o200k, invented shapes; the description with sections minus without; script in
  the PR):

  | shape | per section (#12) | per document | × |
  |---|---|---|---|
  | 20 docs × 12 short sections, ~120-char titles — the theoretical worst | +5 029 tokens | +409 | 12.3 |
  | same, with 120-char titles of one repeated letter | +16 093 | +634 | 25.4 |
  | 4 docs × 12 sections of ~29 chars | +859 | +392 | 2.2 |
  | 1 doc × 12 sections | +229 | +142 | 1.6 |

  **The price, measured on the same shapes:** where the rendered block fills, fewer sections fit
  — 4 docs × 12 leaves 14 of 48 out instead of 6. 1 × 12, 2 × 12 and 6 × 6 lose none.
- Tests (`tests/unit/test_consult_documents_sections.py`):
  - **each title ONCE**: 3 docs × 5 sections → 3 lines, each title once in the block; control:
    all 15 sections there;
  - **the ceiling counts the RENDERED block**: 3 docs × 12 sections of 60 chars → the block
    ≤ 1200 and the next section would cross it; control: the text of what was listed is below
    the block's length;
  - **the worst case is bounded**: 20 docs × 12 → the block ≤ 1200; control: the same sections
    one per line are more than 4× it;
  - the P9.0 tests rewritten to the grouped line (the twin, the defanging, the per-document
    ceiling, the title ceiling); the byte-identity digests unchanged;
  - **the price, asserted by the function**: 1 × 12, 2 × 12 and 6 × 6 leave 0 sections out (every
    one listed), and 4 × 12 leaves exactly 14 of 48 out and says so in `(and 14 more sections)`
    (on `main` the same shapes give 0/0/0/6). Mutation: the budget on the headings' text again
    → the 4 × 12 test red.
- **Mutations, by hand, through the gate** (anchor `grep -cxF` = 1, `ast.parse`, red, reverted):
  - the title repeated per section again (one line per section) →
    `test_TWIN_each_title_is_written_ONCE_its_sections_beside_it`, with the twin, the defanging,
    the ceilings and the worst case (6 failed / 38 passed);
  - the budget counting the heading TEXT again (`add = len(label)`) →
    `test_TWIN_the_total_ceiling_counts_the_RENDERED_block` and the worst case (2 failed / 42
    passed).

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
