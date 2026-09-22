from app.connectors.base import DBConnector
from app.connectors.mysql import MySQLConnector
from app.connectors.postgres import PostgresConnector
from app.connectors.sqlite import SQLiteConnector

_REGISTRY = {
    "postgres": PostgresConnector,
    "mysql": MySQLConnector,
    "sqlite": SQLiteConnector,
}


def build_connector(
    type_: str, host: str, port: int, database: str, username: str, password: str
) -> DBConnector:
    cls = _REGISTRY.get(type_)
    if cls is None:
        raise ValueError(f"Unsupported connection type: {type_!r}")
    return cls(host, port, database, username, password)
