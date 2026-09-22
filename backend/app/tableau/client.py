"""Thin wrapper around tableauserverclient (TSC) for Personal Access Token
auth. Isolated here so publisher.py never touches the SDK directly.

Reuses the Connection model's existing fields for a tableau_server
connection: `host` = server URL, `username` = PAT name, decrypted
`encrypted_secret` = PAT value, `tableau_site_id` = site to sign into.
"""
from __future__ import annotations

from contextlib import contextmanager

import tableauserverclient as TSC


class TableauClient:
    def __init__(self, server_url: str, site_id: str, token_name: str, token_value: str):
        self.server = TSC.Server(server_url, use_server_version=True)
        self._auth = TSC.PersonalAccessTokenAuth(token_name, token_value, site_id or "")

    @contextmanager
    def session(self):
        with self.server.auth.sign_in(self._auth):
            yield self.server

    def test_connection(self) -> None:
        """Raise if the PAT/site/server URL don't actually authenticate."""
        with self.session():
            pass
