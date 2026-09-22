import pytest
from cryptography.fernet import Fernet
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core import security
from app.db.base import Base
from app.db.models.audit_log import AuditLog
from app.db.models.connection import Connection
from app.schemas.connection import ConnectionCreate
from app.services import connection_service


class FakeConnector:
    """Stands in for a real Postgres/MySQL connector so these tests don't
    need a live database - only connection_service's own logic is exercised."""

    def __init__(self, read_only: bool):
        self._read_only = read_only
        self.tested = False

    def test_connection(self) -> None:
        self.tested = True

    def check_read_only(self) -> bool:
        return self._read_only

    def introspect_schema(self):
        return []


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture(autouse=True)
def encryption_key(monkeypatch):
    monkeypatch.setattr(security.settings, "encryption_key", Fernet.generate_key().decode())


def _payload(**overrides):
    defaults = dict(
        name="prod-postgres",
        type="postgres",
        host="db.internal",
        port=5432,
        database_name="analytics",
        username="readonly_user",
        secret="hunter2",
    )
    defaults.update(overrides)
    return ConnectionCreate(**defaults)


def test_create_connection_succeeds_for_readonly_db_user(db, monkeypatch):
    monkeypatch.setattr(connection_service, "build_connector", lambda *a, **k: FakeConnector(read_only=True))

    conn = connection_service.create_connection(db, _payload(), actor="shubhanshu@tnqtech.com")

    assert conn.is_read_only is True
    assert conn.encrypted_secret != b"hunter2"
    assert security.decrypt(conn.encrypted_secret) == "hunter2"

    stored = db.query(Connection).filter_by(id=conn.id).one()
    assert stored.name == "prod-postgres"

    logs = db.query(AuditLog).filter_by(connection_id=conn.id).all()
    assert len(logs) == 1
    assert logs[0].event_type == "connection_created"
    assert logs[0].actor == "shubhanshu@tnqtech.com"


def test_create_connection_rejects_writable_db_user(db, monkeypatch):
    monkeypatch.setattr(connection_service, "build_connector", lambda *a, **k: FakeConnector(read_only=False))

    with pytest.raises(connection_service.ConnectionNotReadOnlyError):
        connection_service.create_connection(db, _payload(), actor="shubhanshu@tnqtech.com")

    assert db.query(Connection).count() == 0
    assert db.query(AuditLog).count() == 0


class FakeTableauClient:
    def __init__(self, *a, **k):
        pass

    def test_connection(self) -> None:
        pass


def test_create_connection_for_tableau_server_skips_readonly_check_but_tests_auth(db, monkeypatch):
    called = {"build_connector": False}

    def fail_if_called(*a, **k):
        called["build_connector"] = True
        raise AssertionError("build_connector should not be called for tableau_server")

    monkeypatch.setattr(connection_service, "build_connector", fail_if_called)
    monkeypatch.setattr(connection_service, "TableauClient", FakeTableauClient)

    conn = connection_service.create_connection(
        db,
        _payload(type="tableau_server", secret="pat-token-value"),
        actor="shubhanshu@tnqtech.com",
    )

    assert called["build_connector"] is False
    assert conn.is_read_only is True
    assert security.decrypt(conn.encrypted_secret) == "pat-token-value"


def test_create_connection_for_tableau_server_rejects_bad_pat(db, monkeypatch):
    class FailingTableauClient(FakeTableauClient):
        def test_connection(self) -> None:
            raise RuntimeError("simulated: invalid personal access token")

    monkeypatch.setattr(connection_service, "TableauClient", FailingTableauClient)

    with pytest.raises(connection_service.ConnectionFailedError):
        connection_service.create_connection(
            db, _payload(type="tableau_server", secret="bad-token"), actor="shubhanshu@tnqtech.com"
        )

    assert db.query(Connection).count() == 0
