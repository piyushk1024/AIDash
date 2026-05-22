import re

DISALLOWED = re.compile(
    r'\b(DROP|DELETE|UPDATE|INSERT|ALTER|TRUNCATE|GRANT|REVOKE|CREATE|REPLACE|EXEC|EXECUTE)\b',
    re.IGNORECASE
)

ALLOWED_START = re.compile(
    r'^\s*(SELECT|WITH)\b',
    re.IGNORECASE
)

def validate_sql(sql: str, context: str = "") -> None:
    """
    Raises ValueError if sql contains disallowed keywords or doesn't start with SELECT/WITH.
    context is an optional label for the error message (e.g. chart title).
    """
    if not ALLOWED_START.match(sql):
        raise ValueError(f"SQL rejected — must start with SELECT or WITH{f' ({context})' if context else ''}")
    match = DISALLOWED.search(sql)
    if match:
        raise ValueError(f"SQL rejected — disallowed keyword '{match.group()}'{f' ({context})' if context else ''}")