from sqlalchemy import create_engine, text

from app.connectors.base import DBConnector, SQLAlchemyConnectorMixin


class PostgresConnector(SQLAlchemyConnectorMixin, DBConnector):
    _system_schemas = {"pg_catalog", "information_schema", "pg_toast"}

    def __init__(self, host: str, port: int, database: str, username: str, password: str):
        url = f"postgresql+psycopg2://{username}:{password}@{host}:{port}/{database}"
        self._engine = create_engine(url, pool_pre_ping=True)

    def check_read_only(self) -> bool:
        # information_schema.table_privileges reflects privileges granted to
        # current_user (directly or via role membership) across all tables
        # it can see. Any of these means the user is NOT read-only.
        query = text(
            """
            SELECT COUNT(*) FROM information_schema.table_privileges
            WHERE grantee = current_user
              AND privilege_type IN ('INSERT', 'UPDATE', 'DELETE', 'TRUNCATE')
            """
        )
        with self._engine.connect() as conn:
            count = conn.execute(query).scalar()
        return count == 0
