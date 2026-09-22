class DomainError(Exception):
    """Base class for errors that should surface as a clear, specific message
    to the user instead of a raw exception/stack trace."""


class IllegalTransitionError(DomainError):
    def __init__(self, current_status: str, target_status: str):
        self.current_status = current_status
        self.target_status = target_status
        super().__init__(
            f"Cannot move flow from '{current_status}' to '{target_status}'."
        )


class SQLValidationError(DomainError):
    """Raised when generated SQL is not a plain read-only SELECT, or fails to parse."""


class ConnectionFailedError(DomainError):
    """Raised when a source DB/Tableau connection cannot be opened or tested.
    Wraps the underlying driver exception so the API returns a clean message
    instead of leaking a raw stack trace / internal connection string."""


class SchemaDriftError(DomainError):
    def __init__(self, table: str, column: str | None = None):
        self.table = table
        self.column = column
        target = f"{table}.{column}" if column else table
        super().__init__(
            f"Schema drift detected: '{target}' referenced by the plan no longer "
            "exists in the live source schema. Re-generate or edit the plan."
        )


class HyperTypeMismatchError(DomainError):
    def __init__(self, offending_columns: dict[str, str]):
        self.offending_columns = offending_columns
        details = ", ".join(f"{c} ({t})" for c, t in offending_columns.items())
        super().__init__(f"Cannot write to Hyper, unsupported/ambiguous types: {details}")


class JoinAnomalyError(DomainError):
    """Raised only when an anomaly is severe enough to hard-block rather than
    just flag `row_count_anomaly` for human review (e.g. preview call misuse)."""


class PublishError(DomainError):
    def __init__(self, message: str, retryable: bool):
        self.retryable = retryable
        super().__init__(message)
