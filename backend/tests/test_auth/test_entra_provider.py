"""Entra External ID provider (#1323): authorization URL, id_token validation.

No network: discovery, JWKS and token endpoint are served by an
`httpx.MockTransport`, and the id_token is signed by an RSA key generated here.
"""
import time
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from joserfc import jwt
from joserfc.jwk import OctKey, RSAKey

from app.core.config import get_settings
from app.services.auth.errors import LoginError
from app.services.auth.idp.entra import EntraIdentityProvider

SUBDOMAIN = "tcnclub"
TENANT_ID = "11111111-2222-3333-4444-555555555555"
CLIENT_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
AUTHORITY = f"https://{SUBDOMAIN}.ciamlogin.com/{TENANT_ID}"
ISSUER = f"https://{TENANT_ID}.ciamlogin.com/{TENANT_ID}/v2.0"
JWKS_URI = f"{AUTHORITY}/discovery/v2.0/keys"
NONCE = "nonce-from-the-round-trip"
ROUND_TRIP = {"verifier": "v" * 43, "nonce": NONCE}

ENTRA_SETTINGS = {
    "AUTH_ENTRA_SUBDOMAIN": SUBDOMAIN,
    "AUTH_ENTRA_TENANT_ID": TENANT_ID,
    "AUTH_ENTRA_CLIENT_ID": CLIENT_ID,
    "AUTH_ENTRA_CLIENT_SECRET": "entra-test-secret",
}

SIGNING_KEY = RSAKey.generate_key(2048, parameters={"kid": "key-1"})


@pytest.fixture(autouse=True)
def entra_configured(monkeypatch):
    for key, value in ENTRA_SETTINGS.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()


def _claims(**overrides) -> dict:
    now = int(time.time())
    claims = {
        "iss": ISSUER,
        "aud": CLIENT_ID,
        "sub": "pairwise-subject-1",
        "oid": "entra-subject-1",
        "iat": now,
        "nbf": now,
        "exp": now + 3600,
        "nonce": NONCE,
        "email": "adherent@exemple.fr",
        "xms_edov": True,
        "name": "Adhérent Test",
    }
    claims.update(overrides)
    return {key: value for key, value in claims.items() if value is not None}


def _id_token(key: RSAKey = SIGNING_KEY, **overrides) -> str:
    header = {"alg": "RS256", "kid": key.kid}
    return jwt.encode(header, _claims(**overrides), key)


def _unsigned_token(header: dict, claims: dict) -> str:
    import base64
    import json

    def segment(part: dict) -> str:
        return base64.urlsafe_b64encode(json.dumps(part).encode()).rstrip(b"=").decode()

    return f"{segment(header)}.{segment(claims)}."


class FakeEntra:
    """Serves discovery, JWKS and token endpoint, and counts the calls."""

    def __init__(
        self,
        id_token: str | None = None,
        keys: list[RSAKey] | None = None,
        discovery: dict | None = None,
    ):
        self.id_token = id_token or _id_token()
        self.keys = keys or [SIGNING_KEY]
        self.discovery = discovery or {"issuer": ISSUER, "jwks_uri": JWKS_URI}
        self.calls: list[str] = []
        self.token_requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        url = str(request.url).split("?")[0]
        self.calls.append(url)
        if url == f"{AUTHORITY}/v2.0/.well-known/openid-configuration":
            return httpx.Response(200, json=self.discovery)
        if url == JWKS_URI:
            return httpx.Response(
                200, json={"keys": [key.as_dict(private=False) for key in self.keys]}
            )
        if url == f"{AUTHORITY}/oauth2/v2.0/token":
            self.token_requests.append(request)
            return httpx.Response(
                200,
                json={
                    "access_token": "access-token",
                    "token_type": "Bearer",
                    "expires_in": 3600,
                    "id_token": self.id_token,
                },
            )
        raise AssertionError(f"unexpected route: {request.url}")

    def count(self, url: str) -> int:
        return self.calls.count(url)


def _provider(handler) -> EntraIdentityProvider:
    return EntraIdentityProvider(transport_factory=lambda: httpx.MockTransport(handler))


def _refused(provider: EntraIdentityProvider, round_trip=ROUND_TRIP) -> str:
    with pytest.raises(LoginError) as refusal:
        provider.fetch_identity(code="code-1", round_trip=round_trip)
    return refusal.value.code


# --- authorize -------------------------------------------------------------


def test_authorize_builds_the_url_without_network():
    def no_network(request: httpx.Request) -> httpx.Response:
        raise AssertionError("authorize must not call the network")

    request = _provider(no_network).authorize(state="state-123")

    url = urlparse(request.url)
    params = parse_qs(url.query)
    assert f"{url.scheme}://{url.netloc}{url.path}" == f"{AUTHORITY}/oauth2/v2.0/authorize"
    assert params["state"] == ["state-123"]
    assert params["response_type"] == ["code"]
    assert params["client_id"] == [CLIENT_ID]
    assert params["redirect_uri"] == ["http://127.0.0.1:3000/api/v1/auth/entra/callback"]
    assert params["scope"] == ["openid profile email"]
    assert params["code_challenge_method"] == ["S256"]
    assert params["code_challenge"]
    assert params["nonce"] == [request.round_trip["nonce"]]
    assert set(request.round_trip) == {"verifier", "nonce"}
    assert "code_verifier" not in params


def test_two_authorizations_do_not_share_verifier_or_nonce():
    provider = _provider(FakeEntra())
    first = provider.authorize(state="a").round_trip
    second = provider.authorize(state="b").round_trip

    assert first["verifier"] != second["verifier"]
    assert first["nonce"] != second["nonce"]


# --- fetch_identity: nominal path -------------------------------------------


def test_a_valid_token_with_a_verified_address_yields_the_identity():
    identity = _provider(FakeEntra()).fetch_identity(code="code-1", round_trip=ROUND_TRIP)

    assert identity.provider == "entra"
    assert identity.subject == "entra-subject-1"
    assert identity.email == "adherent@exemple.fr"
    assert identity.email_verified is True
    assert identity.verified_emails == ("adherent@exemple.fr",)
    assert identity.display_name == "Adhérent Test"


def test_the_token_exchange_sends_code_and_verifier():
    fake = FakeEntra()
    _provider(fake).fetch_identity(code="code-1", round_trip=ROUND_TRIP)

    body = parse_qs(fake.token_requests[0].content.decode())
    assert body["code"] == ["code-1"]
    assert body["code_verifier"] == [ROUND_TRIP["verifier"]]
    assert body["grant_type"] == ["authorization_code"]


def test_discovery_and_jwks_are_cached():
    fake = FakeEntra()
    provider = _provider(fake)

    provider.fetch_identity(code="code-1", round_trip=ROUND_TRIP)
    provider.fetch_identity(code="code-2", round_trip=ROUND_TRIP)

    assert fake.count(f"{AUTHORITY}/v2.0/.well-known/openid-configuration") == 1
    assert fake.count(JWKS_URI) == 1


def test_an_unknown_kid_refreshes_the_jwks_once():
    """Key rotation: a token signed by a new key passes after one refresh."""
    rotated = RSAKey.generate_key(2048, parameters={"kid": "key-2"})
    fake = FakeEntra()
    provider = _provider(fake)
    provider.fetch_identity(code="code-1", round_trip=ROUND_TRIP)

    fake.keys = [SIGNING_KEY, rotated]
    fake.id_token = _id_token(rotated)
    identity = provider.fetch_identity(code="code-2", round_trip=ROUND_TRIP)

    assert identity.subject == "entra-subject-1"
    assert fake.count(JWKS_URI) == 2


def test_a_kid_still_unknown_after_refresh_is_refused_without_looping():
    stranger = RSAKey.generate_key(2048, parameters={"kid": "key-x"})
    fake = FakeEntra(id_token=_id_token(stranger))

    assert _refused(_provider(fake)) == "provider_error"
    assert fake.count(JWKS_URI) <= 2


# --- fetch_identity: invalid tokens ------------------------------------------


@pytest.mark.parametrize(
    "overrides",
    [
        {"iss": "https://login.microsoftonline.com/other/v2.0"},
        {"aud": "another-client"},
        {"nonce": "another-nonce"},
        {"nonce": None},
        {"exp": int(time.time()) - 3600, "iat": int(time.time()) - 7200},
        {"sub": None},
        {"oid": None},
        {"nbf": int(time.time()) + 3600},
    ],
    ids=["iss", "aud", "nonce", "nonce-missing", "exp", "sub-missing", "oid-missing", "nbf-future"],
)
def test_an_invalid_claim_is_a_provider_error(overrides):
    assert _refused(_provider(FakeEntra(id_token=_id_token(**overrides)))) == "provider_error"


def test_a_forged_signature_is_a_provider_error():
    impostor = RSAKey.generate_key(2048, parameters={"kid": "key-1"})
    fake = FakeEntra(id_token=_id_token(impostor))

    assert _refused(_provider(fake)) == "provider_error"


@pytest.mark.parametrize(
    "token",
    [
        jwt.encode(
            {"alg": "HS256", "kid": "key-1"},
            _claims(),
            OctKey.import_key("s" * 32),
            algorithms=["HS256"],
        ),
        _unsigned_token({"alg": "none", "kid": "key-1"}, _claims()),
    ],
    ids=["hs256", "alg-none"],
)
def test_a_token_not_signed_with_rs256_is_a_provider_error(token):
    assert _refused(_provider(FakeEntra(id_token=token))) == "provider_error"


def test_the_subject_is_the_tenant_wide_oid_not_the_pairwise_sub():
    """`sub` changes with the app registration; `oid` is stable across the tenant."""
    identity = _provider(FakeEntra()).fetch_identity(code="code-1", round_trip=ROUND_TRIP)

    assert identity.subject == "entra-subject-1"


@pytest.mark.parametrize(
    "discovery",
    [
        {"issuer": "https://evil.example/" + TENANT_ID + "/v2.0", "jwks_uri": JWKS_URI},
        {"issuer": "https://other.ciamlogin.com/other-tenant/v2.0", "jwks_uri": JWKS_URI},
        {"issuer": ISSUER, "jwks_uri": f"https://evil.example/{TENANT_ID}/keys"},
        {"issuer": ISSUER, "jwks_uri": "https://evil.ciamlogin.com/other-tenant/keys"},
    ],
    ids=["issuer-host", "issuer-tenant", "jwks-host", "jwks-tenant"],
)
def test_a_discovery_document_outside_the_tenant_is_refused(discovery):
    assert _refused(_provider(FakeEntra(discovery=discovery))) == "provider_error"


def test_a_round_trip_without_nonce_is_refused():
    """Authlib skips the nonce check when the expected value is empty."""
    assert _refused(_provider(FakeEntra()), {"verifier": "v" * 43}) == "provider_error"


def test_a_token_response_without_id_token_is_a_provider_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"access_token": "a", "token_type": "Bearer"})

    assert _refused(_provider(handler)) == "provider_error"


# --- fetch_identity: unverified address --------------------------------------


@pytest.mark.parametrize(
    "overrides",
    [
        {"email": None}, {"xms_edov": None}, {"xms_edov": False}, {"xms_edov": "true"},
        {"email": None, "idp": "google.com"},
        {"xms_edov": False, "idp": "facebook.com"}, {"xms_edov": False, "idp": "Google.com"},
    ],
    ids=[
        "no-email", "no-xms_edov", "xms_edov-false", "xms_edov-string",
        "google-without-email", "other-idp", "idp-not-exact",
    ],
)
def test_an_address_not_established_as_verified_is_not_certified(overrides):
    identity = _provider(FakeEntra(id_token=_id_token(**overrides))).fetch_identity(
        code="code-1", round_trip=ROUND_TRIP
    )

    assert identity.email_verified is False
    assert identity.verified_emails == ()


def test_an_address_federated_from_google_is_certified():
    """FR-021 measured on the preview: `xms_edov` is false for a gmail.com address,
    since it speaks of the domain owner; Google only hands out verified addresses."""
    identity = _provider(
        FakeEntra(id_token=_id_token(xms_edov=False, idp="google.com"))
    ).fetch_identity(code="code-1", round_trip=ROUND_TRIP)

    assert identity.email_verified is True
    assert identity.verified_emails == ("adherent@exemple.fr",)


def test_an_uncertified_address_logs_the_claim_names_never_the_address(caplog):
    """FR-021 on the preview: tell which claim is missing without logging the address."""
    with caplog.at_level("WARNING"):
        _provider(FakeEntra(id_token=_id_token(xms_edov=None))).fetch_identity(
            code="code-1", round_trip=ROUND_TRIP
        )

    message = next(r.getMessage() for r in caplog.records if "certified" in r.getMessage())
    assert "email" in message and "xms_edov=None" in message and "idp=None" in message
    assert "@" not in message


# --- fetch_identity: network --------------------------------------------------


def test_an_unreachable_provider_is_provider_unavailable():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("unreachable")

    assert _refused(_provider(handler)) == "provider_unavailable"


def test_a_token_endpoint_5xx_without_json_is_provider_unavailable():
    fake = FakeEntra()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/oauth2/v2.0/token"):
            return httpx.Response(503, text="<html>Service Unavailable</html>")
        return fake(request)

    assert _refused(_provider(handler)) == "provider_unavailable"


def test_an_unreachable_jwks_is_provider_unavailable():
    fake = FakeEntra()

    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == JWKS_URI:
            return httpx.Response(503)
        return fake(request)

    assert _refused(_provider(handler)) == "provider_unavailable"


# --- configuration -------------------------------------------------------------


@pytest.mark.parametrize("missing", sorted(ENTRA_SETTINGS))
def test_each_of_the_four_settings_is_required(monkeypatch, missing):
    assert EntraIdentityProvider().is_configured() is True

    monkeypatch.setenv(missing, "")
    get_settings.cache_clear()

    assert EntraIdentityProvider().is_configured() is False


def test_the_default_transport_is_the_guarded_one():
    """FR-022: the exemption in `test_core_http._FABRIQUES` rests on this."""
    from app.core import http

    assert EntraIdentityProvider()._transport_factory is http.guarded_transport


def test_entra_is_a_member_method(client):
    methods = client.get("/api/v1/auth/methods").json()
    entra = next(method for method in methods if method["slug"] == "entra")
    assert entra["audience"] == "member"


def test_methods_list_entra_only_when_configured(client, monkeypatch):
    methods = client.get("/api/v1/auth/methods").json()
    assert "entra" in [method["slug"] for method in methods]

    monkeypatch.setenv("AUTH_ENTRA_CLIENT_SECRET", "")
    get_settings.cache_clear()

    slugs = [method["slug"] for method in client.get("/api/v1/auth/methods").json()]
    assert "entra" not in slugs


# --- full round trip over HTTP --------------------------------------------------


def test_the_callback_opens_a_session_with_entra(client, db_session, monkeypatch):
    from app.api.v1.auth import session_cookie_name
    from app.services.auth import session
    from app.services.auth.idp import registry

    fake = FakeEntra()
    monkeypatch.setitem(registry.PROVIDERS, "entra", _provider(fake))

    start = client.get("/api/v1/auth/entra/authorize", follow_redirects=False)
    params = parse_qs(urlparse(start.headers["location"]).query)
    fake.id_token = _id_token(nonce=params["nonce"][0])

    response = client.get(
        f"/api/v1/auth/entra/callback?code=code-1&state={params['state'][0]}",
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["location"] == f"{get_settings().auth_redirect_base_url}/"
    user = session.resolve(db_session, client.cookies[session_cookie_name(get_settings())])
    assert user is not None
    assert user.email == "adherent@exemple.fr"
