"""AST-based SQL safety checks using a real SQL parser (sqlglot).

Replaces fragile substring matching with structural validation:

- only read-only SELECT queries (optionally using CTEs / set operations) are allowed;
- queries may reference only an allow-list of tables (CTE names are excluded);
- string literals or column names that merely *contain* a SQL keyword
  (e.g. a column named "deleted_at", or ``WHERE note = 'DROP TABLE'``) are no
  longer mistaken for dangerous statements.

All checks fail closed: SQL that cannot be parsed and proven safe is rejected.
"""
import sqlglot
from sqlglot import exp

from src.constants import ALLOWED_TABLES
from src.exceptions import SQLGenerationError, SQLSafetyBlockedError
from src.utils.logger import get_logger

logger = get_logger(__name__)

# The database is PostgreSQL; parse with that dialect so Postgres-specific
# syntax (e.g. ``'30 days'::interval``, double-quoted identifiers) is understood.
SQL_DIALECT = "postgres"

# Root AST node types that represent read-only queries.
_READ_ONLY_ROOTS = (exp.Select, exp.Union)


def _parse_single(sql: str) -> exp.Expression:
    """Parse ``sql`` into exactly one AST statement.

    Args:
        sql: SQL string to parse

    Returns:
        The single parsed statement expression

    Raises:
        SQLGenerationError: if the SQL cannot be parsed, is empty, or contains
            more than one statement
    """
    try:
        statements = [s for s in sqlglot.parse(sql, read=SQL_DIALECT) if s is not None]
    except Exception as exc:  # sqlglot raises ParseError and friends
        raise SQLGenerationError(f"Rejected: SQL could not be parsed ({exc}).")

    if not statements:
        raise SQLGenerationError("Rejected: no SQL statement found.")
    if len(statements) > 1:
        raise SQLGenerationError("Rejected: multiple SQL statements detected.")
    return statements[0]


def _referenced_tables(statement: exp.Expression) -> set:
    """Return the real table names referenced, excluding CTE aliases.

    A ``WITH t AS (...) SELECT * FROM t`` query references ``t`` only as a
    common table expression, not as a physical table, so it must not be
    checked against the table allow-list.
    """
    cte_aliases = {cte.alias_or_name.lower() for cte in statement.find_all(exp.CTE)}
    tables = {table.name.lower() for table in statement.find_all(exp.Table)}
    return tables - cte_aliases


def is_read_only(sql: str) -> bool:
    """Return True if ``sql`` is a single read-only (SELECT) statement."""
    try:
        statement = _parse_single(sql)
    except SQLGenerationError:
        return False
    return isinstance(statement, _READ_ONLY_ROOTS)


def uses_only_allowed_tables(sql: str, allowed_tables=ALLOWED_TABLES) -> bool:
    """Return True if ``sql`` references only tables in the allow-list."""
    try:
        statement = _parse_single(sql)
    except SQLGenerationError:
        return False
    allowed = {t.lower() for t in allowed_tables}
    return _referenced_tables(statement).issubset(allowed)


def guard_sql(sql: str, allowed_tables=ALLOWED_TABLES) -> str:
    """Validate that ``sql`` is a safe, read-only query over allowed tables.

    Args:
        sql: SQL string to validate
        allowed_tables: iterable of permitted table names

    Returns:
        The ``sql`` unchanged if it passes every check

    Raises:
        SQLGenerationError: if the SQL is unparseable or not a single statement
            (a generation/formatting issue, not a security concern).
        SQLSafetyBlockedError: if the SQL is parseable but violates a safety
            rule — it is not read-only, or it references a table outside the
            allow-list.
    """
    statement = _parse_single(sql)

    if not isinstance(statement, _READ_ONLY_ROOTS):
        kind = type(statement).__name__.upper()
        raise SQLSafetyBlockedError(f"Rejected: only SELECT queries are allowed (got {kind}).")

    allowed = {t.lower() for t in allowed_tables}
    disallowed = sorted(_referenced_tables(statement) - allowed)
    if disallowed:
        raise SQLSafetyBlockedError(
            f"Rejected: query references table(s) not in the allow-list: {disallowed}."
        )

    return sql
