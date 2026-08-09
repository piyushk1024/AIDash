import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError

DIALECT = "postgres"

DISALLOWED_NODE_TYPES = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Drop,
    exp.Alter,
    exp.Create,
    exp.TruncateTable,
    exp.Grant,
    exp.Command,  # catches unparsed/DDL-ish statements sqlglot doesn't model explicitly
)

def validate_sql(sql: str, expected_table: str, context: str = "") -> None:
    """
    Parses sql into an AST and raises ValueError unless it is a single
    SELECT/WITH statement containing no disallowed node types, and every
    table reference resolves to expected_table (CTE aliases excluded).
    context is an optional label for the error message (e.g. chart title).
    """
    label = f" ({context})" if context else ""

    try:
        statements = sqlglot.parse(sql, read=DIALECT)
    except ParseError as e:
        raise ValueError(f"SQL rejected — could not parse{label}: {e}")

    statements = [s for s in statements if s is not None]
    if len(statements) != 1:
        raise ValueError(f"SQL rejected — must be a single statement{label}")

    root = statements[0]
    if not isinstance(root, exp.Select):
        raise ValueError(f"SQL rejected — must start with SELECT or WITH{label}")

    cte_names = {cte.alias_or_name for cte in root.find_all(exp.CTE)}

    for node in root.walk():
        if isinstance(node, DISALLOWED_NODE_TYPES):
            raise ValueError(f"SQL rejected — disallowed operation '{type(node).__name__}'{label}")
        if isinstance(node, exp.Table):
            table_name = node.name
            if table_name in cte_names:
                continue
            if table_name != expected_table:
                raise ValueError(
                    f"SQL rejected — references table '{table_name}', expected '{expected_table}'{label}"
                )