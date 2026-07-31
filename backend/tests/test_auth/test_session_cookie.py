"""Tests for the session cookie sign/verify helpers (issue #114)."""


def test_sign_then_verify_roundtrip():
    from app.services import auth_service

    token = auth_service.sign_session("secret-key", user_id=42)
    assert auth_service.verify_session("secret-key", token, max_age=60) == 42


def test_tampered_signature_is_rejected():
    from app.services import auth_service

    token = auth_service.sign_session("secret-key", user_id=42)
    tampered = token[:-1] + ("A" if token[-1] != "A" else "B")

    assert auth_service.verify_session("secret-key", tampered, max_age=60) is None


def test_wrong_secret_key_is_rejected():
    from app.services import auth_service

    token = auth_service.sign_session("secret-key", user_id=42)
    assert auth_service.verify_session("other-key", token, max_age=60) is None


def test_expired_cookie_is_rejected(monkeypatch):
    """Freeze itsdangerous' clock (its `time` attribute is the `time` module)."""
    import itsdangerous.timed as timed_mod

    from app.services import auth_service

    fake_time = [1_000_000.0]

    class _Clock:
        @staticmethod
        def time():
            return fake_time[0]

    monkeypatch.setattr(timed_mod, "time", _Clock)

    token = auth_service.sign_session("secret-key", user_id=42)
    fake_time[0] += 120

    assert auth_service.verify_session("secret-key", token, max_age=60) is None


def test_state_cookie_uses_a_separate_salt():
    """Signing a value as `session` must not verify as `state` and vice versa."""
    from app.services import auth_service

    session_token = auth_service.sign_session("secret-key", user_id=42)
    state_token = auth_service.sign_state("secret-key", state="abc")

    assert auth_service.verify_state("secret-key", session_token, max_age=60) is None
    assert auth_service.verify_session("secret-key", state_token, max_age=60) is None
