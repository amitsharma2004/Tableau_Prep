from __future__ import annotations

from sqlalchemy import create_engine, inspect, text

from app.connectors.base import ColumnInfo, DBConnector, SQLAlchemyConnectorMixin, TableInfo, quote_identifier


class SQLiteConnector(SQLAlchemyConnectorMixin, DBConnector):
    _system_schemas = set()

    def __init__(self, host: str, port: int, database: str, username: str, password: str):
        # For SQLite, 'database' represents the path to the .db file
        # host/port/username/password are optional/ignored for local SQLite files
        url = f"sqlite:///{database}"
        self._engine = create_engine(url)

    def check_read_only(self) -> bool:
        # SQLite local file connector for testing/dev is accepted as read-only
        return True

    def introspect_schema(self) -> list[TableInfo]:
        inspector = inspect(self._engine)
        tables: list[TableInfo] = []
        for table_name in inspector.get_table_names():
            columns = [
                ColumnInfo(
                    name=col["name"],
                    data_type=str(col["type"]),
                    nullable=bool(col["nullable"]),
                )
                for col in inspector.get_columns(table_name)
            ]
            tables.append(TableInfo(name=table_name, schema="main", columns=columns))
        return tables

    def sample_rows(self, table: str, schema: str | None, limit: int) -> list[dict]:
        with self._engine.connect() as conn:
            result = conn.execute(text(f"SELECT * FROM {quote_identifier(table)} LIMIT :limit"), {"limit": limit})
            return [dict(row._mapping) for row in result]
