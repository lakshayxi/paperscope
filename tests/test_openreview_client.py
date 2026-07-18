import paperscope.openreview_client as orc


def test_auth_mode_guest_when_no_credentials(monkeypatch):
    monkeypatch.delenv("OPENREVIEW_TOKEN", raising=False)
    monkeypatch.delenv("OPENREVIEW_USERNAME", raising=False)
    monkeypatch.delenv("OPENREVIEW_PASSWORD", raising=False)
    assert orc.auth_mode() == "guest"


def test_auth_mode_token_takes_priority(monkeypatch):
    monkeypatch.setenv("OPENREVIEW_TOKEN", "sometoken")
    monkeypatch.setenv("OPENREVIEW_USERNAME", "user@example.com")
    monkeypatch.setenv("OPENREVIEW_PASSWORD", "pw")
    assert orc.auth_mode() == "token"


def test_auth_mode_password_when_no_token(monkeypatch):
    monkeypatch.delenv("OPENREVIEW_TOKEN", raising=False)
    monkeypatch.setenv("OPENREVIEW_USERNAME", "user@example.com")
    monkeypatch.setenv("OPENREVIEW_PASSWORD", "pw")
    assert orc.auth_mode() == "password"


def test_credentials_dict_shape(monkeypatch):
    monkeypatch.delenv("OPENREVIEW_TOKEN", raising=False)
    monkeypatch.delenv("OPENREVIEW_USERNAME", raising=False)
    monkeypatch.delenv("OPENREVIEW_PASSWORD", raising=False)
    assert orc._credentials() == {}


def test_reset_clients_clears_cache():
    orc._client_v1 = "not none"
    orc._client_v2 = "not none"
    orc.reset_clients()
    assert orc._client_v1 is None
    assert orc._client_v2 is None
