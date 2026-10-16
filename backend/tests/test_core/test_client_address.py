"""Client IP behind Vercel, Cloudflare and Render (#1533).

The `X-Forwarded-For` shapes below are the ones measured on the preview backend
on 2026-10-16: the caller's own entries first, then the address Cloudflare saw,
then the Cloudflare edge and the Render internal hop.
"""
from types import SimpleNamespace

from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from app.core.client_address import ClientAddressMiddleware, rate_limit_key

REAL = "90.49.125.30"
VERCEL_EGRESS = "13.38.74.191"
TAIL = ", 172.71.119.62, 10.28.198.73"
SECRET = "s3cret-proxy-value"


def _client(**settings):
    async def echo(request):
        return JSONResponse(
            {"client": request.client.host if request.client else None, "scheme": request.url.scheme}
        )

    app = Starlette(routes=[Route("/", echo)])
    config = SimpleNamespace(**{"trusted_proxy_count": 3, "frontend_proxy_secret": None, **settings})
    app.add_middleware(ClientAddressMiddleware, settings=config)
    return TestClient(app)


def _seen(client, **headers):
    return client.get("/", headers=headers).json()["client"]


def test_a_forged_leading_entry_does_not_change_the_client():
    client = _client()

    assert _seen(client, **{"X-Forwarded-For": f"{REAL}{TAIL}"}) == REAL
    assert _seen(client, **{"X-Forwarded-For": f"203.0.113.9,{REAL}{TAIL}"}) == REAL
    assert _seen(client, **{"X-Forwarded-For": f"203.0.113.1, 203.0.113.2,{REAL}{TAIL}"}) == REAL


def test_several_header_lines_are_read_as_one_list():
    client = _client()
    response = client.get(
        "/", headers=[("X-Forwarded-For", "203.0.113.9"), ("X-Forwarded-For", f"{REAL}{TAIL}")]
    )

    assert response.json()["client"] == REAL


def test_a_chain_shorter_than_the_proxies_keeps_the_socket_peer():
    """Outside the platform (local dev, tests) nothing in the header is trusted."""
    client = _client()

    assert _seen(client, **{"X-Forwarded-For": "203.0.113.9, 198.51.100.1"}) == "testclient"
    assert _seen(client) == "testclient"


def test_zero_trusted_proxies_ignores_the_header():
    client = _client(trusted_proxy_count=0)

    assert _seen(client, **{"X-Forwarded-For": f"203.0.113.9,{REAL}{TAIL}"}) == "testclient"


def test_without_secret_the_vercel_rewrite_counts_as_its_egress_ip():
    client = _client()

    seen = _seen(
        client,
        **{"X-Forwarded-For": f"{REAL},{VERCEL_EGRESS}{TAIL}", "X-Vercel-Forwarded-For": "203.0.113.9"},
    )

    assert seen == VERCEL_EGRESS


def test_the_vercel_rewrite_keeps_one_bucket_per_visitor():
    client = _client(frontend_proxy_secret=SECRET)

    def via_front(visitor):
        return _seen(
            client,
            **{
                "X-Forwarded-For": f"{visitor},{VERCEL_EGRESS}{TAIL}",
                "X-Vercel-Forwarded-For": visitor,
                "X-Frontend-Proxy-Secret": SECRET,
            },
        )

    assert via_front("198.51.100.1") == "198.51.100.1"
    assert via_front("198.51.100.2") == "198.51.100.2"


def test_a_wrong_secret_does_not_unlock_the_vercel_header():
    client = _client(frontend_proxy_secret=SECRET)

    seen = _seen(
        client,
        **{
            "X-Forwarded-For": f"{REAL}{TAIL}",
            "X-Vercel-Forwarded-For": "203.0.113.9",
            "X-Frontend-Proxy-Secret": "guess",
        },
    )

    assert seen == REAL


def test_an_invalid_vercel_header_falls_back_to_the_forwarded_chain():
    client = _client(frontend_proxy_secret=SECRET)

    seen = _seen(
        client,
        **{
            "X-Forwarded-For": f"{REAL},{VERCEL_EGRESS}{TAIL}",
            "X-Vercel-Forwarded-For": "not-an-ip",
            "X-Frontend-Proxy-Secret": SECRET,
        },
    )

    assert seen == VERCEL_EGRESS


def test_forwarded_proto_still_sets_the_scheme():
    client = _client()

    assert client.get("/", headers={"X-Forwarded-Proto": "https"}).json()["scheme"] == "https"
    assert client.get("/", headers={"X-Forwarded-Proto": "gopher"}).json()["scheme"] == "http"


def test_forwarded_proto_keeps_the_last_value():
    client = _client()

    assert client.get("/", headers={"X-Forwarded-Proto": "http, https"}).json()["scheme"] == "https"


def test_a_hop_count_drift_is_logged(caplog):
    """On both measured paths Cloudflare's peer sits at the chosen position: a
    mismatch means the platform changed its number of hops."""
    client = _client(frontend_proxy_secret=SECRET)

    with caplog.at_level("WARNING", logger="app.core.client_address"):
        _seen(client, **{"X-Forwarded-For": f"{REAL}{TAIL}", "CF-Connecting-IP": REAL})
        assert not caplog.records
        drifted = f"203.0.113.9,{REAL}, 10.28.198.73"
        _seen(client, **{"X-Forwarded-For": drifted, "CF-Connecting-IP": REAL})

    assert "TRUSTED_PROXY_COUNT" in caplog.text


def test_a_missing_secret_is_logged_at_startup(caplog):
    with caplog.at_level("WARNING", logger="app.core.client_address"):
        with _client():
            pass
        assert "FRONTEND_PROXY_SECRET" in caplog.text
        caplog.clear()
        with _client(frontend_proxy_secret=SECRET):
            pass
        assert not caplog.records


def test_two_ipv6_addresses_in_one_64_share_a_rate_limit_key():
    """#1552: a /64 can rotate its source address on every request."""
    assert rate_limit_key("2001:db8:1:2::1") == rate_limit_key("2001:db8:1:2:ffff:ffff:ffff:fffe")
    assert rate_limit_key("2001:db8:1:2::1") == "2001:db8:1:2::/64"


def test_different_ipv6_64_prefixes_get_different_keys():
    assert rate_limit_key("2001:db8:1:2::1") != rate_limit_key("2001:db8:1:3::1")


def test_ipv4_keys_on_the_full_address():
    assert rate_limit_key("90.49.125.30") == "90.49.125.30"


def test_ipv4_mapped_ipv6_keys_as_its_ipv4():
    assert rate_limit_key("::ffff:90.49.125.30") == "90.49.125.30"


def test_a_non_ip_host_is_kept_as_is():
    assert rate_limit_key("testclient") == "testclient"
    assert rate_limit_key("2001:db8::zz") == "2001:db8::zz"


def test_a_6to4_address_keys_as_its_ipv4():
    """One IPv4 owns the whole 2002:<v4>::/48, i.e. 65,536 /64 prefixes."""
    assert rate_limit_key("2002:102:304:1::1") == rate_limit_key("2002:102:304:2::1") == "1.2.3.4"
