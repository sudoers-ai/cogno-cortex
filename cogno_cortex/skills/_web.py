"""What the two web skills share: the personal-data screen, the digest, the cache and the record.

Private on purpose (``_web``): a host imports :mod:`cogno_cortex.skills.web_search` and
:mod:`cogno_cortex.skills.web_fetch`, which re-export what it needs. Nothing here does I/O.

**Personal data never leaves through a web call.** A search query and a URL are text the MODEL
wrote, and both go to a third party: the search provider, and the site plus every server on the
way. The house rule is that personal data may come IN and never goes OUT, so before either call
the text is read by the ecosystem's one deterministic detector
(:func:`cogno_anima.security.detector.default_detector` unless the host injects another): any
finding refuses the call. The refusal names the CLASSES found (a closed vocabulary), never the
value. The detector is the whole of anima's definition of personal data, IP addresses and card
numbers included, so a query that names an IP address is refused too, and so is a URL whose path
carries a long number that passes the card checksum. A refusal costs the executor one rephrase; a
leak cannot be taken back.

**The cache is the process's and a host partitions it.** :class:`TTLCache` is bounded (oldest out
first) and expires by an injected clock. The key carries the caller's ``scope``, so a host that
passes its tenant never serves one tenant a cache entry another tenant's call paid for. Nothing is
persisted.
"""

from __future__ import annotations

import hashlib
import time
import unicodedata
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Callable, Hashable, Iterable, Optional

from cogno_anima.security.detector import PiiDetector, default_detector
from cogno_anima.security.prompt_guard import sanitize_untrusted

#: What one call came to — the ``outcome`` of a :class:`WebRecord`.
OUTCOME_RESULTS = "results"            # search: hits came back; fetch: a page's text came back
OUTCOME_EMPTY = "empty"                # search: no hit; fetch: the page carries no readable text
OUTCOME_PII_BLOCKED = "pii_blocked"    # personal data in the query/URL: nothing was sent
OUTCOME_QUOTA = "quota_exceeded"       # the host's allowance refused the call: nothing was sent
OUTCOME_REFUSED = "refused"            # a fetch guard refused (scheme, address, size, type, …)
OUTCOME_FAILED = "failed"              # the provider or the transport raised
OUTCOME_INVALID = "invalid"            # nothing usable to search or fetch
VALID_OUTCOMES: "frozenset[str]" = frozenset({
    OUTCOME_RESULTS, OUTCOME_EMPTY, OUTCOME_PII_BLOCKED, OUTCOME_QUOTA, OUTCOME_REFUSED,
    OUTCOME_FAILED, OUTCOME_INVALID})

#: The cache's default bound: entries, not bytes (a fetch entry is capped at its text ceiling).
DEFAULT_CACHE_ENTRIES = 512

_DETECTOR: Optional[PiiDetector] = None


def _default_detector() -> PiiDetector:
    global _DETECTOR
    if _DETECTOR is None:
        _DETECTOR = default_detector()
    return _DETECTOR


def personal_data(texts: Iterable[str], detector: Optional[PiiDetector] = None) -> "tuple[str, ...]":
    """The personal-data CLASSES found in any of ``texts``, sorted, each once. ``()`` = clean.

    Never the value: the caller renders the classes, which come from the detector's closed
    vocabulary, and nothing else."""
    det = detector or _default_detector()
    found: "set[str]" = set()
    for text in texts:
        if text:
            found.update(det.detect(text))
    return tuple(sorted(found))


def normalise(text: str) -> str:
    """The text a cache key and a digest are taken over: NFKC, case-folded, whitespace collapsed."""
    return " ".join(unicodedata.normalize("NFKC", str(text or "")).casefold().split())


def digest(text: str) -> str:
    """16 hex characters of SHA-256 over :func:`normalise` — what a log line carries instead of
    the text. An unsalted digest of a short query is de-identification, not secrecy: it groups
    repeats of one query, and a reader who guesses the query can confirm the guess. That is why a
    query REFUSED for personal data is never digested at all."""
    return hashlib.sha256(normalise(text).encode("utf-8")).hexdigest()[:16]


def label(text: Any, names: "set[str]", limit: int) -> str:
    """Third-party text as ONE safe line: whitespace collapsed, made inert for the turn's tool
    names (:func:`sanitize_untrusted`), cut to ``limit`` characters."""
    one = " ".join(str(text or "").split())
    one = " ".join(sanitize_untrusted(one, names).split())
    return one if len(one) <= limit else one[:limit - 1].rstrip() + "…"


class TTLCache:
    """A bounded, expiring, in-process cache. ``clock`` is injectable (seconds, monotonic).

    ``get`` answers ``None`` for a missing or expired key; ``put`` evicts the oldest entry past
    ``max_entries``. Not thread-safe — it lives inside one event loop, like the host's other
    per-process caches."""

    def __init__(self, ttl_s: float, *, max_entries: int = DEFAULT_CACHE_ENTRIES,
                 clock: Callable[[], float] = time.monotonic) -> None:
        if isinstance(ttl_s, bool) or not isinstance(ttl_s, (int, float)) or ttl_s <= 0:
            raise ValueError("ttl_s must be a positive number of seconds")
        if isinstance(max_entries, bool) or not isinstance(max_entries, int) or max_entries < 1:
            raise ValueError("max_entries must be a positive int")
        self.ttl_s = float(ttl_s)
        self.max_entries = max_entries
        self._clock = clock
        self._items: "OrderedDict[Hashable, tuple[float, Any]]" = OrderedDict()

    def get(self, key: Hashable) -> Any:
        item = self._items.get(key)
        if item is None:
            return None
        stamped, value = item
        if self._clock() - stamped >= self.ttl_s:
            del self._items[key]
            return None
        return value

    def put(self, key: Hashable, value: Any) -> None:
        self._items[key] = (self._clock(), value)
        self._items.move_to_end(key)
        while len(self._items) > self.max_entries:
            self._items.popitem(last=False)

    def __len__(self) -> int:
        return len(self._items)


@dataclass(frozen=True)
class WebRecord:
    """One call of a web skill, content-free: what a host's ledger and trace read after the turn.

    Appended to the list the host PRE-PLACED on the access (``records``). No query, no URL, no
    text: ``query_sha`` is :func:`digest` (``""`` when the query was refused for personal data),
    ``host`` is the host name of the page fetched (``""`` before one was known).

    * ``provider_calls`` — how many times the PAID provider was called by this call: ``0`` on a
      cache hit, a refusal or a quota refusal; ``1`` when the provider was asked, whether it
      answered or raised (a provider bills the request it received).
    * ``reason`` — a closed label on a refusal (``REASON_*`` of the fetch module) or the exception
      CLASS name on a failure; ``""`` otherwise.
    * ``pii_types`` — the classes that refused the call (:func:`personal_data`).
    """

    tool: str
    outcome: str
    reason: str = ""
    query_sha: str = ""
    host: str = ""
    results: int = 0
    chars: int = 0
    provider_calls: int = 0
    cached: bool = False
    redirects: int = 0
    pii_types: "tuple[str, ...]" = ()


def append_record(records: Optional[list], record: WebRecord) -> None:
    if records is not None:
        records.append(record)
