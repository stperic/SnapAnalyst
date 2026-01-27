"""
SQL Validator

Validates and checks SQL queries for safety and correctness.

This is business logic for SQL validation, not UI-specific.
"""


def is_direct_sql(text: str) -> bool:
    """
    Check if the text appears to be a direct SQL query.

    Args:
        text: User input to check

    Returns:
        True if text starts with SQL keywords (SELECT, WITH)
    """
    text_stripped = text.strip().upper()
    return text_stripped.startswith('SELECT') or text_stripped.startswith('WITH')


def validate_readonly_sql(sql: str) -> tuple[bool, str]:
    """
    Validate that SQL is read-only (only SELECT/WITH allowed).

    Args:
        sql: SQL query to validate

    Returns:
        Tuple of (is_valid, error_message)
        - (True, "") if valid read-only SQL
        - (False, "error message") if contains write operations
    """
    sql_upper = sql.upper()

    # List of forbidden write operations
    forbidden_keywords = [
        'INSERT', 'UPDATE', 'DELETE', 'DROP', 'ALTER',
        'CREATE', 'TRUNCATE', 'REPLACE', 'MERGE', 'GRANT',
        'REVOKE', 'EXEC', 'EXECUTE'
    ]

    for keyword in forbidden_keywords:
        if keyword in sql_upper:
            return False, (
                f"⚠️ Direct SQL queries are read-only. '{keyword}' statements are not allowed.\n\n"
                "Please use SELECT or WITH statements only, or use natural language for your question."
            )

    return True, ""
