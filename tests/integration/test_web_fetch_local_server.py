"""``web_fetch`` end to end over the SYSTEM resolver and a real local server — no injected
resolver, no stand-in transport: the address comes from the operating system's own lookup of
``localhost`` (``/etc/hosts``; nothing leaves the box) and the guard has to judge it.

The server is a subprocess on a disposable port, killed by PID at the end of the module.
"""

from __future__ import annotations

import ipaddress

import pytest

from cogno_cortex import build_dispatcher
from cogno_cortex.skills.web_fetch import (
    META_WEB_FETCH_ACCESS,
    REASON_ADDRESS,
    WEB_FETCH,
    WEB_FETCH_MANIFEST,
    WebFetchAccess,
    system_resolver,
)
from tests.web_support import LocalServer

LOOPBACK = (ipaddress.ip_network("127.0.0.0/8"), ipaddress.ip_network("::1/128"))


@pytest.fixture(scope="module")
def server():
    srv = LocalServer()
    try:
        yield srv
    finally:
        srv.stop()


async def test_the_system_resolver_names_localhost_and_the_guard_refuses_it(server):
    addresses = await system_resolver("localhost", server.port)
    assert addresses and all(ipaddress.ip_address(a).is_loopback for a in addresses)
    records: list = []
    acc = WebFetchAccess(ports=frozenset({server.port}), records=records)
    disp = build_dispatcher([WEB_FETCH_MANIFEST], metadata={META_WEB_FETCH_ACCESS: acc})
    before = server.count()
    res = await disp.execute(WEB_FETCH, {"url": f"http://localhost:{server.port}/page.html"})
    assert not res.ok and records[0].reason == REASON_ADDRESS
    assert server.count() == before


async def test_with_loopback_opened_the_same_page_is_read_end_to_end(server):
    records: list = []
    acc = WebFetchAccess(ports=frozenset({server.port}), allow_networks=LOOPBACK,
                         records=records)
    disp = build_dispatcher([WEB_FETCH_MANIFEST], metadata={META_WEB_FETCH_ACCESS: acc})
    res = await disp.execute(WEB_FETCH, {"url": f"http://127.0.0.1:{server.port}/redirect/1"})
    assert res.ok and "leaves at 07:40" in res.output and "SCRIPT-SENTINEL" not in res.output
    assert records[0].redirects == 2 and records[0].host == "127.0.0.1"
