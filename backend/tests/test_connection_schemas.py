from app.schemas.connection import ConnectionRead


def test_connection_read_never_exposes_secret_fields():
    field_names = set(ConnectionRead.model_fields.keys())
    assert "secret" not in field_names
    assert "encrypted_secret" not in field_names
    assert "password" not in field_names
