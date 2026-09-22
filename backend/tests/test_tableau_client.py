from contextlib import contextmanager

import pytest

from app.tableau import client as client_module
from app.tableau.client import TableauClient


class FakeAuth:
    def __init__(self, should_fail=False):
        self.should_fail = should_fail

    @contextmanager
    def sign_in(self, auth):
        if self.should_fail:
            raise RuntimeError("simulated: authentication failed")
        yield "fake-session"


class FakeServer:
    def __init__(self, server_url, use_server_version=True, should_fail=False):
        self.server_url = server_url
        self.auth = FakeAuth(should_fail=should_fail)


def test_session_yields_server_on_successful_sign_in(monkeypatch):
    monkeypatch.setattr(client_module.TSC, "Server", lambda url, use_server_version=True: FakeServer(url))
    monkeypatch.setattr(client_module.TSC, "PersonalAccessTokenAuth", lambda name, value, site: object())

    tc = TableauClient("https://tableau.example.com", "my-site", "token-name", "token-value")

    with tc.session() as server:
        assert server is tc.server


def test_test_connection_raises_on_bad_credentials(monkeypatch):
    monkeypatch.setattr(client_module.TSC, "Server", lambda url, use_server_version=True: FakeServer(url, should_fail=True))
    monkeypatch.setattr(client_module.TSC, "PersonalAccessTokenAuth", lambda name, value, site: object())

    tc = TableauClient("https://tableau.example.com", "my-site", "token-name", "bad-token")

    with pytest.raises(RuntimeError):
        tc.test_connection()
