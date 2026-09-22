import pytest

from app.connectors.base import quote_identifier


@pytest.mark.parametrize(
    "name",
    ["orders", "customer_id", "_private", "Table1"],
)
def test_quote_identifier_allows_safe_names(name):
    assert quote_identifier(name) == f'"{name}"'


@pytest.mark.parametrize(
    "name",
    [
        'orders"; DROP TABLE orders; --',
        "orders; DELETE FROM customers",
        "orders ",
        "",
        "1orders",
        'a"b',
    ],
)
def test_quote_identifier_rejects_unsafe_names(name):
    with pytest.raises(ValueError):
        quote_identifier(name)
