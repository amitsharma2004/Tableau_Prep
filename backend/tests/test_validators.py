import pytest

from app.connectors.base import ColumnInfo, TableInfo
from app.core.errors import SchemaDriftError, SQLValidationError
from app.llm.plan_schema import PlanDraft
from app.transform.validators import check_schema_drift, validate_select_only
from tests.test_plan_schema import VALID_PLAN

LIVE_TABLES = [
    TableInfo(
        name="orders",
        schema="public",
        columns=[
            ColumnInfo(name="id", data_type="INTEGER", nullable=False),
            ColumnInfo(name="customer_id", data_type="INTEGER", nullable=False),
            ColumnInfo(name="amount", data_type="NUMERIC", nullable=False),
            ColumnInfo(name="region", data_type="TEXT", nullable=True),
        ],
    ),
    TableInfo(
        name="customers",
        schema="public",
        columns=[
            ColumnInfo(name="id", data_type="INTEGER", nullable=False),
            ColumnInfo(name="email", data_type="TEXT", nullable=True),
        ],
    ),
]


# --- validate_select_only: defense-in-depth against wrong/destructive SQL ---


def test_validate_select_only_accepts_plain_select():
    validate_select_only("SELECT * FROM orders")


def test_validate_select_only_accepts_cte_select():
    validate_select_only('WITH "x" AS (SELECT * FROM orders) SELECT * FROM "x"')


@pytest.mark.parametrize(
    "malicious_sql",
    [
        "DROP TABLE orders",
        "DELETE FROM orders WHERE 1=1",
        "UPDATE orders SET amount = 0",
        "INSERT INTO orders (id) VALUES (1)",
        "SELECT * FROM orders; DROP TABLE orders",  # multi-statement smuggling
        "ALTER TABLE orders ADD COLUMN hacked TEXT",
    ],
)
def test_validate_select_only_rejects_destructive_statements(malicious_sql):
    with pytest.raises(SQLValidationError):
        validate_select_only(malicious_sql)


def test_validate_select_only_rejects_unparseable_sql():
    with pytest.raises(SQLValidationError):
        validate_select_only("SELECT FROM WHERE ;;; garbage %%%")


# --- check_schema_drift: bad/renamed column or table caught before execution ---


def test_check_schema_drift_passes_for_matching_schema():
    plan = PlanDraft.model_validate(VALID_PLAN)
    check_schema_drift(plan, LIVE_TABLES)  # must not raise


def test_check_schema_drift_detects_missing_table():
    plan_dict = dict(VALID_PLAN)
    plan_dict["sources"] = [
        {"alias": "orders", "schema_name": "public", "table_name": "orders_renamed"},
        *VALID_PLAN["sources"][1:],
    ]
    plan = PlanDraft.model_validate(plan_dict)

    with pytest.raises(SchemaDriftError):
        check_schema_drift(plan, LIVE_TABLES)


def test_check_schema_drift_detects_missing_column_referenced_by_join():
    plan_dict = dict(VALID_PLAN)
    plan_dict["steps"] = [
        {
            "type": "join",
            "left": "orders",
            "right": "customers",
            "join_type": "inner",
            "on": [["customer_id_typo", "id"]],  # bad column, real one is customer_id
            "output_alias": "joined",
        }
    ]
    plan_dict["output_alias"] = "joined"
    plan = PlanDraft.model_validate(plan_dict)

    with pytest.raises(SchemaDriftError):
        check_schema_drift(plan, LIVE_TABLES)


def test_check_schema_drift_ignores_columns_on_intermediate_step_output():
    # "joined" is a step output_alias, not a live table - referencing an
    # arbitrary column on it must NOT be flagged as drift here (out of scope
    # for this MVP validator, see docstring).
    plan_dict = dict(VALID_PLAN)
    plan_dict["steps"] = VALID_PLAN["steps"] + [
        {
            "type": "select_columns",
            "target": "result",
            "output_alias": "final",
            "columns": ["anything_at_all"],
        }
    ]
    plan_dict["output_alias"] = "final"
    plan = PlanDraft.model_validate(plan_dict)

    check_schema_drift(plan, LIVE_TABLES)  # must not raise
