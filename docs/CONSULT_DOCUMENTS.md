# `consult_documents` — search the documents a business published

`cogno_cortex.skills.consult_documents` (extra `documents`, which pulls `cogno-engram`). The
module docstring is the long form; this page is the contract a host wires against.

## What it is — and what it is not

A skill that embeds the question, asks a `cogno_engram.DocumentStore` for passages, keeps the
ones above a relevance floor and hands them to the executor, each with where it came from. It is
**mechanism only**: it knows no tenant, persona, role, plan or price. Everything that decides
WHO reads WHAT is injected by the host, and nothing the model writes can change it.

It is not a memory or graph search. Documents are text somebody wrote to be read by a group;
they share no store and no read with a contact's memories or the knowledge graph.

## The contract

```python
from cogno_cortex.skills.consult_documents import (
    CONSULT_DOCUMENTS,        # "consult_documents" — the tool name
    META_DOCUMENTS_ACCESS,    # "documents_access" — the ONE metadata key the skill reads
    DocumentsAccess,          # what the host injects (frozen, validated at construction)
    ConsultRecord,            # what one call spent and found (content-free)
    MODE_PASSAGES, MODE_SECTION, MODE_DOCUMENT, VALID_MODES,   # how the documents were shown
    MIN_HEADING_WORDS,        # 2 — content words a section heading needs to be evidence
    OUTCOME_CONTINUED, OUTCOME_UNREADABLE,                      # a continuation's outcomes
    offer_consult_documents,  # async: manifest for this reader, or None
    describe_documents,       # pure: the tool description from the readable titles (+ sections)
    consult_documents_manifest,
    ConsultDocumentsTool,     # the BaseTool; its only argument is `query`
    render_excerpts,          # pure: the payload renderer
)
```

| `DocumentsAccess` field | Meaning |
|---|---|
| `store` | a `DocumentStore` (structural) — `search` and `readable_documents` are used |
| `embedder` | `embed_with_usage(text) -> (vector, tokens)`, else `embed(text) -> vector` |
| `embed_model` | `cogno_engram.embed_model_label(spec, width)` of THAT embedder; must match the store's width |
| `owner_key` | the store's opaque owner; blank → `ValueError` |
| `profile` | the READER's label; blank → `ValueError` (there is no wildcard reader) |
| `hybrid_floor`, `lexical_floor` | **required**, in `[0, 1]` — see *The floor* |
| `lexical_evidence_floor` | **required**, in `[0, 1]` — see *The evidence gate*; `0` = off |
| `user_text` | the contact's raw turn; searched beside `query`, never rendered |
| `limit` | passages asked of the store per search (default 3) |
| `max_excerpt_chars`, `max_answer_chars` | the budget (defaults 2400 / 7200) |
| `tool_names` | the turn's exposed tool set, for `sanitize_untrusted` |
| `records` | a list the host pre-placed; one `ConsultRecord` is appended per call |
| `max_whole_chars` | the budget of an answer that reads documents whole (P9); `0` (default) = off — no `whole`/`document`/`after` in the schema, the passages byte for byte; when set, ≥ `MIN_ANSWER_CHARS` and the store must have `read_served` |
| `whole_doc_chars` | a document of the passed passages with at most this much text is read whole without being asked (`0` = only on `whole: true`); ≤ `max_whole_chars` |
| `section_mode` | for a document longer than `whole_doc_chars`, the union of the level-2 blocks holding its passages; `False` by default (see *Reading a document whole*) |

## Two gates

* **The table** — `offer_consult_documents(access)` returns `None` when this reader has no ready,
  readable document. Then the tool is not offered: a tool that can only answer "nothing here"
  teaches the executor to promise a lookup it can never complete.
* **Execute** — every search passes `access.profile` and `access.owner_key` to the store, which
  filters by them. A manifest built for one reader and executed with another reader's access
  reads what the second may read. The model's arguments cannot reach either value: the tool
  declares only `query`, and extra arguments are dropped (not refused — a refusal would be a
  validation error inside the provider, a crashed turn).

## The description: titles, and the sections under them

`describe_documents(documents, *, tool_names=(), sections=None)` builds what the EXECUTOR reads
to decide whether to call the tool at all. A title alone often does not say what a document
covers, and a tool the executor cannot see to be about the question is a tool it does not
choose — measured on a reference host: a request about a subject that lived only in a SECTION
was sent to this tool 0/3 with titles alone (the other tool got it 3/3) and 3/3 with the sections
listed, while a request that belonged to the other tool went there 3/3 in both arms.

* **Titles**, as always: one line each, `sanitize_untrusted` + excerpt-fence tags defanged, cut
  to `MAX_TITLE_CHARS`, JSON string literals, at most `MAX_TITLES_IN_DESCRIPTION` (the rest
  counted).
* **`sections`** maps a document's **id** to its headings (by id: two documents may share a
  title; anything but a mapping is no sections). Each heading goes through the SAME label rule
  as a title, and they are written under the titles **one line per document** — the title ONCE,
  its sections beside it: `"Title": "Section"; "Other section"`. Ceilings:
  `MAX_SECTION_CHARS` (60) per section, `MAX_SECTIONS_PER_DOCUMENT` (12), and
  `MAX_SECTIONS_CHARS` (1200) characters of the section BLOCK **as rendered** (titles, quotes,
  separators, line breaks) — what the executor is actually sent; the first section that does not
  fit ends its document's line. The rest are **counted** (`(and N more sections)`), those of a
  document past the title ceiling included. Every number is at most a scope guard's, so a host
  that hands over the sections its guard rendered can only see FEWER here, never one the guard
  did not.
* **Why one line per document (P9.0-b).** The first form wrote one line per SECTION, each
  repeating its title, and bounded the section TEXT only. Measured (o200k, invented shapes, the
  description with sections minus without):

  | shape | one line per section | one line per document |
  |---|---|---|
  | 20 documents × 12 short sections, ~120-char titles (the theoretical worst) | +5 029 tokens | +409 |
  | 4 documents × 12 sections of ~29 chars | +859 | +392 |
  | 1 document × 12 sections | +229 | +142 |

  The price, measured on the same shapes: when the rendered block is full, fewer sections fit —
  the 4 × 12 shape leaves 14 of 48 out instead of 6; the 1 × 12, 2 × 12 and 6 × 6 shapes lose
  none.
* **With no section to write** (`None`, `{}`, none for the listed documents) the description is
  the titles-only one **byte for byte** — pinned by digest against the bytes before this change.
* **Personal data is the caller's filter.** A heading comes from the file's CONTENT, not from
  the upload form, so it was never checked; this skill cannot tell a name from a word. The host
  hands over only headings it has filtered — and `offer_consult_documents` passes **none**.

## Two searches, fused by the maximum

The question exists twice: in the contact's words (the documents' language) and in the model's
`query` (a canonical rewrite, but carrying the turn's context — *"and on Saturday?"* →
*"Saturday opening hours"*). Both are searched and a passage keeps the better of its two scores;
the floor applies to that fused score. The five rules, each pinned by its own test:

1. **One search when they are the same** after `cogno_engram.textfold.fold(punctuation=True,
   collapse_whitespace=True)`, or when either is blank.
2. **A tie goes to the contact's words** (`hit_variants` says `user`).
3. **Any failed embedding → BOTH searches go without a vector**, so the two results share a scale.
4. **Any lexical result → every passage is scored by its `lexical_score`**, and the lexical floor
   applies. (A model swap committing between the two searches can produce that shape.)
5. **A failed search still records the tokens spent** (`outcome="search_failed"`): what is billed
   is what HAPPENED.

## The floor

The store returns RAW scores in `[0, 1]`, without a floor, on one of two scales: hybrid (vector +
words) or lexical (words only, marked `kb_embed_space_unavailable`). A number calibrated on one
scale means nothing on the other, so there are two floors and the skill picks by the mark (or by
its own knowledge that it had no vector). **There is no default**: the values come from a
labelled evaluation over the distribution these scores actually have, and a default written here
first would become the value every caller ships.

## The floor's one exception: evidence by the HEADING (hybrid mode)

A section that IS a table — years and figures, little prose — scores low on both halves of a
hybrid score even when it is the answer. Measured on a reference host: the passage that answered
came back FIRST, with a fused score of 0.361 under a hybrid floor of 0.40 (vector 0.490, lexical
0.167 — enough for the evidence gate below, whose floor there is 0.13), and the same 0.361 with
the section's exact heading as the query. The record said `cut_by=floor`, `below_floor=3`, and
the contact was told the documents did not say — about the one passage that did.

What such a passage carries is its section HEADING. So, **in hybrid mode**, a passage below the
floor **passes** when its section heading names the question:

* **the heading** is the leaf of the passage's `heading_path` — a SECTION's; a passage under the
  document title alone has none (the title is the head of the path, the rule the provenance
  header applies);
* **the words** are `cogno_engram.lexical.terms` — the engram's one tokenizer and stopword list,
  over the general text fold (`cogno_engram.textfold.fold`: case, accents, compatibility forms),
  the fold the in-memory index uses and the one this skill already compares its two variants
  with; a digits-only token (an outline's `12.`, a table's years) is not a content word. The
  Postgres index folds in SQL (`portuguese` + `unaccent`, which also stems): that has no
  client-side twin, so the heading test does not claim to be the index's measure — it is the
  engram's word rule, on both sides;
* **names** means EVERY content word of the heading is in ONE of the texts searched (the model's
  `query` or the contact's words — not spread over the two), and the heading has at least
  `MIN_HEADING_WORDS` (2) of them;
* **or the other way round** — the question IN the heading: EVERY *subject* word of ONE of the
  texts searched is in the heading, and that text has at least ONE. A subject word is a content
  word that is not digits-only and not one of a business's FRAME words — the ecosystem's one list
  of those, `cogno_anima.stages.scope_options.GENERIC_SUBJECT_WORDS`, compared as it is compared
  there (cut to `EVIDENCE_PREFIX` = 6 characters; no list of this skill's own). This is the short
  question that names its subject: measured on a reference host, a question of one subject word
  read three passages, ALL under the hybrid floor (`cut_by=floor`), from a document whose sections
  «9. *Subject* — Investment» and «10. *Subject* — Rental income» were the answer — and the first
  direction can never fire there, because each heading carries a word the question does not. A
  question whose only words are frame words («School?», «Documents?») names nothing and lifts
  nothing.

**Why a floor of two words, not a list of generic headings.** One word shared with a question is
exactly the evidence the rule refuses everywhere else — a heading of several words matched by
ONE of them does not pass — so a one-word heading (*General*, *Other*) would be that same single
word under another name. A list of generic headings is a list per language, and it fails OPEN on
the word it forgot. The price is said, not hidden: a SPECIFIC one-word heading (*Parking*) does
not get the exception from the first direction, and is judged by the floor as before — unless
the question's subject words are ALL in it (*Parking?*), which is the second direction.

**The question verbs are frame words (anima 0.1.1).** «O que sabe sobre o *X*?» used to keep
«sabe» as a subject word: the shared list had «saber», and at six characters «sabe» is not
«saber», so the contact's sentence alone named a word no heading has. anima #207 put the question
verbs (sabe, sabem, conhece, fala, falam, falar) in the shared list, and this repo requires
`cogno-anima>=0.1.1`: the sentence now names only its subject and, by itself, rescues the subject's sections.
`test_TWIN_the_literal_sentence_with_sabe_is_rescued_by_itself` pins it. The price comes with the
list: «conhecimento» cuts to the same six characters as «conhece», so «base de conhecimento» names
no subject either.

What it does **not** change:

* the floor holds for every other passage;
* a rescued passage only fills a slot the floor left empty (the reading shows at most `limit`),
  so every passage it lets in is SHOWN, and the order stays the score's — all of them sit below
  everything that cleared the floor;
* it still faces the evidence gate;
* a **lexical** result is untouched: its floor already is a words test, and the exception was
  measured on the hybrid scale only;
* with nothing rescued the record, the payload and the evidence are the old ones byte for byte
  (pinned by digest against the tree before the change), and `cut_by` is what it always was.

The record counts it: `heading_match` is how many passages passed by heading, and `below_floor`
keeps counting every passage that scored under the floor — so the floor cut
`below_floor - heading_match`. The evidence line gains `heading_match=N` only when `N > 0`.
**Its price:** a question that repeats a section's heading word for word lifts that section from
under the floor even when the section does not hold the answer; it is shown with its provenance,
and the executor reads it.

## The evidence gate (hybrid mode)

The vector half of a hybrid score measures TOPIC, and topic alone can lift a passage over the
floor: a question about something the documents never mention lands near the passage about the
nearest thing they do mention. A floor on the fused score cannot tell the two apart, and one
measured to lose nothing on one corpus can cut real answers on another. So, **in hybrid mode**,
among the passages that CLEAR the floor (a passage let in by its heading included), at least one
must also share the question's words — its
`lexical_score` must reach `lexical_evidence_floor` — or the reading is *nothing relevant*.

* The gate reads the **set** that cleared the floor, never only its first passage.
* It only **decides**: when it lets the reading through, the passages shown, their order and
  their scores are exactly the ones the floor alone would give.
* The word test is the **store's** own lexical measure, under the store's own fold (the one its
  index uses — `portuguese` + `unaccent` on Postgres, the general text fold in memory), so
  *Sábado* and *sabado* are the same evidence.
* It does **not** apply to a lexical result: there the floor already is a lexical threshold.
* **Its price:** a passage that answers purely by paraphrase — no word in common with either text
  searched — is now *nothing relevant*. `0` switches the gate off.

The record says which gate cut (`cut_by`: `floor` | `lexical_evidence`), with the evidence it
read (`lexical_evidence`, the highest `lexical_score` among the passages that cleared the floor)
and each shown passage's `lexical_scores`.

## Reading a document whole (P9)

The best passages answer a question about ONE fact; a summary, a syllabus or «everything the
document says about X» needs the document. Measured on a reference host over 20 labelled
questions: the best-3 passages carried the expected content completely in 16, reading the
documents of the shown passages whole in 20 — the documents served there were small (the largest
~2.1 k tokens). With `max_whole_chars` set:

* **Document mode.** For the documents of the passages that PASSED, in the order of their best
  passage: a document whose text is ≤ `whole_doc_chars` is read WHOLE and shown as ONE excerpt
  (`[n] kb:<document>.<version> · Title · whole document`), its section headings in line
  (`## Section › Sub · page N`) and the chunks' overlap said once
  (`cogno_engram.chunking.join_passages`), while it fits `max_whole_chars`. A document that does
  not fit keeps its passages; what fits nowhere is counted.
* **`whole: true`** — the optional argument «when the contact asks for the summary or the complete
  content of a document»: the documents are read whole whatever their size, up to the budget. A
  document the budget CUTS ends with `[continues: document=<id>, after=<ordinal>]`, outside the
  excerpt. No extra model call: the executor decides.
* **Continuation.** `document` + `after` (from that mark) read the next slice — no search, no
  embedding, the overlap with the slice before said once. Past the end: a success that says the
  reading had reached its end.
* **Section mode** (`section_mode`, OFF by default): for a document longer than
  `whole_doc_chars`, the UNION of the level-2 blocks (`heading_path[:2]`) of ALL its shown
  passages, `[…]` between blocks that are not contiguous. The block of the best passage alone
  measured 14/20, below the passages' 16/20; the union is here to be measured forced, and it
  enters only if it does not lose to the passages.
* **The reader path, always.** Every whole read is `read_served` with the access's profile, on
  every call: another profile's document, a draft, another owner's or a made-up id reads
  nothing — `status="error"`, outcome `unreadable`, the SAME answer for all of them, so a forged
  `document` learns nothing. The administrator's `version_text` is never used here.
* **A negative never expands.** *Nothing relevant* (by the floor or by the evidence gate) returns
  before any of this; not one whole read happens.
* **Off, or nothing expanded → today's bytes.** With `max_whole_chars = 0`, or when no document
  was expanded, the payload is the passages exactly as before (pinned by digest).
* **A whole read that fails** keeps the passages the search found and marks the record
  `whole_read_unavailable` — the search worked, so it is not an error.

## What the executor reads

```
Passages from the documents this business published, best match first. …
[1] kb:<document>.<version>.<ordinal> · Handbook › Timetable › Saturday · page 4
<excerpt id="kb:<document>.<version>.<ordinal>">
We open from 8 to 12 on Saturday.
</excerpt>
```

or `Nothing in the documents this business published answers this: …` — `status="success"`,
because the documents WERE read and that grounds a negative answer. Failures are `status="error"`
and say not to be read as an absence: an unwired access, an empty question, a store that raised.
An embedder failure is NOT an error — the search degrades to words.

Titles, headings and passages are the business's own text: collapsed to one line where they are
labels, passed through `cogno_anima`'s `sanitize_untrusted`, and stripped of anything that would
open or close an `<excerpt>` fence. Titles in the description are written as JSON string
literals. Whether a title may carry personal data is a publishing rule the HOST enforces when the
document is saved; this skill cannot tell a name from a word.

## What it spends

`CortexDispatcher` carries only the result text to the executor — `SkillResult.usage` never
reaches a host that runs the skill through it. So each call appends a `ConsultRecord` to
`access.records`: `embedding_tokens` (summed over its one or two calls), `embedding_calls`,
`usage_reported` (`False` = unknown, not zero), the variants searched (their LABELS, `user` /
`model` — never the texts), which floor, the outcome, the degradations, how many fused passages
the floor cut (`below_floor`), which gate cut a *nothing relevant* (`cut_by`) and the lexical
evidence it read, how many passed the floor by their heading (`heading_match`; `below_floor`
still counts them), the ids/scores/lexical scores/variants of the passages that passed, and how
many of those fitted the answer (`shown`; with a whole reading, how many of them the answer
COVERS), how the documents were shown (`mode`: `passages` | `section` | `document`), which were
read whole (`whole_ids`), whether the budget cut one (`has_more`), whether this call was a
continuation (`continued`; outcomes `continued` / `unreadable`) and whether the executor asked
for the whole (`whole_requested`) — never text (`ConsultRecord`, pinned in
`tests/unit/test_consult_documents.py`). Who pays, against which allowance, is the host's.

## What stays with the host

Which store and embedder, the owner key, the reader's profile, the two floor values and the
evidence floor, which section headings (already filtered) go into the description, the contact's
raw turn, whether the tool is listed in a scope guard's tool table (use the same `offer` result),
the ledger line for each record, and the publishing rules for documents and titles.
