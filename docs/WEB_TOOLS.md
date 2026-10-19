# `web_search` and `web_fetch` — the two web skills

Two read-only skills (`mutating=False`, `destructive=False`: no confirmation gate ever holds
them). Both are MECHANISM: they know no tenant, plan, key or price. Everything that is policy
arrives from the host in one access object per skill.

| | `web_search` | `web_fetch` |
|---|---|---|
| module | `cogno_cortex.skills.web_search` | `cogno_cortex.skills.web_fetch` |
| extra | none | `web` (`httpx`, `trafilatura`) |
| what the model fills | `query`, `max_results` (≤ 5) | `url`, `max_chars` (default 6000, ceiling 20000) |
| metadata key | `META_WEB_SEARCH_ACCESS` | `META_WEB_FETCH_ACCESS` |
| access | `WebSearchAccess` | `WebFetchAccess` |
| manifest | `WEB_SEARCH_MANIFEST` | `WEB_FETCH_MANIFEST` |

An argument the model invents is dropped by the argument model. An access that is missing is an
error the executor reads as "not available", never as "nothing found".

## The provider (`web_search`)

`SearchProvider` is one async method, `search(query, n) -> list[SearchHit]`, where `SearchHit` is
`(title, url, snippet)`. The host builds it: the API client, its key, its timeout. The library
reads no environment variable. `FakeSearchProvider` answers from a table and records every
`(query, n)` it received — the test double, and how a test proves a refused query was never sent.

A provider (or the wrapper a host puts around one) raises `SearchQuotaExceeded` when the caller's
allowance refuses the call before anything is sent; the executor is told the daily limit was
reached. Any other exception is a FAILED search, said as such. Neither is cached. A hit whose URL
is not `http`/`https` is dropped.

## Personal data never goes out

Before a query is sent, and before a URL is requested (on every redirect hop too), the text is
read by the anima's deterministic detector (`cogno_anima.security.detector.default_detector`,
or the one the host injects as `detector`). For a URL that is the path, the query string and the
fragment, raw and percent-decoded. Any finding refuses the call:

- `status="error"`, evidence `web_search:pii_blocked` / `web_fetch:pii_blocked`;
- the payload names the CLASSES found (`EMAIL`, `PHONE`, `NATIONAL_ID`, …) and tells the executor
  to try again without them; it never repeats the value;
- the record's `pii_types` carries the classes and its `query_sha` stays empty.

The detector is the whole of anima's definition of personal data. Its costs, declared: a query
naming an IP address is refused, and so is a URL whose path carries a long number that passes the
card checksum. A refusal costs one rephrase.

## The fetch guards (SSRF and the rest)

Checked before any byte is requested, and again on every redirect hop:

| guard | refusal `reason` |
|---|---|
| scheme `http`/`https` only | `scheme` |
| no `user:password@` in the URL | `credentials` |
| port in `WebFetchAccess.ports` (default 80, 443) | `port` |
| the host name resolves | `host` |
| EVERY address it resolves to is public (`is_global`, not multicast; IPv4-mapped IPv6 read as IPv4) | `address` |
| at most 3 redirects, each with a `Location` | `redirects` |
| status below 400 | `status` |
| `Content-Type` is `text/html`, `text/plain` or `application/xhtml+xml` | `content_type` |
| at most 2 MB, counted decoded, read in a stream | `too_large` |
| the whole call within 10 s | `timeout` |

The connection goes to the address that was CHECKED: the URL is rewritten to that address, the
original name travels in the `Host` header and as the TLS server name, so the certificate is still
verified for the name and a second DNS answer cannot redirect the request (DNS rebinding). Each
hop is a fresh client: no cookie travels, no authentication is sent, and no proxy or `.netrc` is
read from the environment (`trust_env=False`). The request carries its own `User-Agent`.

`WebFetchAccess.allow_networks` is the one exception to the public-address rule, EMPTY by default:
a test server, or an intranet a host decides to open, named network by network. The other limits
(`timeout_s`, `max_bytes`, `max_redirects`, `max_chars_ceiling`) can only be tightened.

## Extraction

`text/plain` is returned as it is. HTML goes through `trafilatura` when it is installed and finds
text, and otherwise through `strip_tags`, a standard-library parser that drops `script`, `style`,
`noscript` and the other non-text elements WITH their content and keeps the `<title>`. The record
does not say which ran; the result's evidence does (`extractor=trafilatura|strip|plain`).

## What the executor reads

Third-party text, made inert for the turn's tool names (`sanitize_untrusted`) — a page or a snippet
that spells a tool call cannot trigger one — and cut: titles, URLs and snippets to one bounded
line each, a page to `max_chars` with a `[…page text truncated…]` mark. The anima fences tool
output again in every prompt it reaches. An empty result (no hit; a page with no text) is a real
reading and says so.

## The cache

`TTLCache` is in process memory, bounded (512 entries by default, oldest out first) and expires by
an injected clock: one hour for a search (`DEFAULT_CACHE_TTL_S` of `web_search`), ten minutes for a
page (that of `web_fetch`). The host keeps one per process and passes it on the access, with a
`scope`: the scope is part of every key, so a host that passes its tenant never serves one tenant
an entry another paid for. A failure or a refusal is never cached. Nothing is persisted.

## The record

One `WebRecord` per execute, appended to the list the host pre-placed (`records=`), content-free:
`tool`, `outcome` (`results | empty | pii_blocked | quota_exceeded | refused | failed | invalid`),
`reason` (the refusal's closed label, or the exception's CLASS name), `query_sha` (16 hex of
SHA-256 over the normalised query; empty when refused for personal data), `host` (the page's host
name), `results`, `chars`, `provider_calls` (`1` when the paid provider was asked, whether it
answered or raised; `0` on a cache hit, a refusal, a quota refusal), `cached`, `redirects`,
`pii_types`. A host bills from `provider_calls` and counts from `outcome`; this library prices
nothing.

## What stays with the host

The provider and its key, the daily allowance (raise `SearchQuotaExceeded`), the price per call
and the ledger row, who may hold the tools (plan, persona, role), the cache's lifetime in the
process, and any per-tenant list of allowed or blocked domains (not implemented here).
