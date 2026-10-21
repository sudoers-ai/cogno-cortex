# Logging in cogno-cortex

This library follows the Cogno house rule: **libraries emit, the host configures.**

- Every module that logs takes its logger from `logging.getLogger(__name__)` and emits lazy
  `key=value` messages. The library installs **no** handlers/formatters and never
  calls `basicConfig`.
- The host attaches its handler and sets the level per package, e.g.
  `logging.getLogger("cogno_cortex").setLevel(logging.INFO)`.

## Level policy
- **ERROR** — never emitted. The bus raises `SkillNotFoundError` / `RuntimeError`
  (no provider); `CortexDispatcher` maps an unknown tool to a recoverable
  `ToolResult(ok=False)`. The host decides how to surface failures.
- **WARNING** — recoverable issues only: `event=skill_import_failed` when a skill
  `.py` fails to import (the loader skips it and continues);
  `event=consult_documents_embed_unavailable error=<ExceptionType|width>` when the
  question could not be embedded (the search degrades to words);
  `event=consult_documents_search_failed error=<ExceptionType>` when the document
  store raised (the tool answers with an error);
  `event=consult_documents_whole_read_failed error=<ExceptionType>` when reading a document
  WHOLE raised (the answer keeps the passages the search found; the record carries
  `whole_read_unavailable`);
  `event=consult_documents_read_failed error=<ExceptionType>` when a continuation
  (`document` + `after`) raised (the tool answers with an error). Never an id, a title or text.
  `event=web_search_pii_blocked types=<count>` / `event=web_fetch_pii_blocked types=<count>` when
  a query or a URL carried personal data (nothing was sent; no digest is logged);
  `event=web_search_quota_exceeded query_sha=<16 hex>` when the host's allowance refused;
  `event=web_search_failed query_sha=<16 hex> error=<ExceptionType>` when the provider raised;
  `event=web_fetch_refused reason=<closed label> host=<host name|->` when a fetch guard refused;
  `event=web_fetch_failed error=<ExceptionType>` when the transport raised. Never a query, a URL,
  a path, a title, a snippet or page text.
- **INFO** — none.
- **DEBUG** — `event=skill_invoked name=… provider=… status=…` per bus dispatch;
  `event=web_search_done query_sha=<16 hex> results=<count> cached=<0|1>` and
  `event=web_fetch_done host=<host name> chars=<count> cached=<0|1>` per successful web call.

## What gets logged
- `cogno_cortex.bus` — DEBUG `event=skill_invoked`.
- `cogno_cortex.loader` — WARNING `event=skill_import_failed`.
- `cogno_cortex.skills.consult_documents` — the four `consult_documents_*` WARNINGs
  above (six call sites): an exception TYPE or a width, never the question, a title or a
  passage.
- `cogno_cortex.skills.web_search` — WARNING `web_search_pii_blocked`, `web_search_quota_exceeded`,
  `web_search_failed`; DEBUG `web_search_done`.
- `cogno_cortex.skills.web_fetch` — WARNING `web_fetch_pii_blocked`, `web_fetch_refused`,
  `web_fetch_failed`; DEBUG `web_fetch_done`. The host NAME of the page (never its URL) is the one
  value of third-party origin a line carries: it is what an operator needs to see which site
  refused or failed.
- `cogno_cortex`, `cogno_cortex.skills`, `cogno_cortex.skills._web` and
  `cogno_cortex.{types,base,registry,dispatcher}` — nothing.

`query_sha` is 16 hex characters of SHA-256 over the normalised query: de-identification, not
secrecy — a reader who guesses a query can confirm the guess. That is why a query refused for
personal data is never digested.

Skill arguments, payloads and prompt bodies are **never** logged (only the skill
name, provider label, and status). Token usage rides on `SkillResult.usage`, not in
logs (metering is `cogno-meter`'s job).
