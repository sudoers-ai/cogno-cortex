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
    offer_consult_documents,  # async: manifest for this reader, or None
    describe_documents,       # pure: the tool description from the readable titles
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
| `user_text` | the contact's raw turn; searched beside `query`, never rendered |
| `limit` | passages asked of the store per search (default 3) |
| `max_excerpt_chars`, `max_answer_chars` | the budget (defaults 2400 / 7200) |
| `tool_names` | the turn's exposed tool set, for `sanitize_untrusted` |
| `records` | a list the host pre-placed; one `ConsultRecord` is appended per call |

## Two gates

* **The table** — `offer_consult_documents(access)` returns `None` when this reader has no ready,
  readable document. Then the tool is not offered: a tool that can only answer "nothing here"
  teaches the executor to promise a lookup it can never complete.
* **Execute** — every search passes `access.profile` and `access.owner_key` to the store, which
  filters by them. A manifest built for one reader and executed with another reader's access
  reads what the second may read. The model's arguments cannot reach either value: the tool
  declares only `query`, and extra arguments are dropped (not refused — a refusal would be a
  validation error inside the provider, a crashed turn).

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
`usage_reported` (`False` = unknown, not zero), the variants searched, which floor, the outcome,
the degradations, and the ids/scores/variants of the passages that passed — never text. Who pays,
against which allowance, is the host's.

## What stays with the host

Which store and embedder, the owner key, the reader's profile, the two floor values, the contact's
raw turn, whether the tool is listed in a scope guard's tool table (use the same `offer` result),
the ledger line for each record, and the publishing rules for documents and titles.
