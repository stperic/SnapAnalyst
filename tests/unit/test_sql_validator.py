"""
Unit tests for SQL Validator

Tests SQL security validation and direct SQL detection.
"""

from src.utils.sql_validator import is_direct_sql, validate_readonly_sql


class TestIsDirectSQL:
    """Test direct SQL detection"""

    def test_select_statement(self):
        """Test detection of SELECT statement"""
        assert is_direct_sql("SELECT * FROM households") is True
        assert is_direct_sql("select * from households") is True
        assert is_direct_sql("  SELECT * FROM households  ") is True

    def test_with_statement(self):
        """Test detection of WITH (CTE) statement"""
        assert is_direct_sql("WITH cte AS (SELECT * FROM h) SELECT * FROM cte") is True
        assert is_direct_sql("with cte as (select 1) select 1") is True
        assert is_direct_sql("  WITH cte AS (SELECT 1) SELECT 1  ") is True

    def test_natural_language_not_sql(self):
        """Test that natural language is not detected as SQL"""
        assert is_direct_sql("What is the error rate?") is False
        assert is_direct_sql("Show me the top 10 states") is False
        assert is_direct_sql("How many households are there?") is False

    def test_sql_keywords_in_middle(self):
        """Test that SQL keywords in middle of text are not detected"""
        assert is_direct_sql("I want to select the best option") is False
        assert is_direct_sql("Working with data from 2023") is False

    def test_empty_string(self):
        """Test handling of empty string"""
        assert is_direct_sql("") is False
        assert is_direct_sql("   ") is False

    def test_case_insensitive(self):
        """Test case-insensitive detection"""
        assert is_direct_sql("SeLeCt * FrOm households") is True
        assert is_direct_sql("WiTh cte AS (SELECT 1) SELECT 1") is True


class TestValidateReadonlySQL:
    """Test read-only SQL validation"""

    def test_valid_select_query(self):
        """Test valid SELECT query passes"""
        sql = "SELECT * FROM households WHERE fiscal_year = 2023"
        is_valid, error = validate_readonly_sql(sql)

        assert is_valid is True
        assert error == ""

    def test_valid_with_query(self):
        """Test valid WITH (CTE) query passes"""
        sql = """
        WITH state_totals AS (
            SELECT state_name, SUM(snap_benefit) as total
            FROM households
            GROUP BY state_name
        )
        SELECT * FROM state_totals
        """
        is_valid, error = validate_readonly_sql(sql)

        assert is_valid is True
        assert error == ""

    def test_valid_complex_select(self):
        """Test complex SELECT with joins passes"""
        sql = """
        SELECT h.state_name, COUNT(*) as error_count
        FROM households h
        JOIN qc_errors e ON h.case_id = e.case_id
        WHERE h.fiscal_year = 2023
        GROUP BY h.state_name
        ORDER BY error_count DESC
        LIMIT 10
        """
        is_valid, error = validate_readonly_sql(sql)

        assert is_valid is True
        assert error == ""

    def test_reject_insert(self):
        """Test INSERT statement is rejected"""
        sql = "INSERT INTO households (case_id) VALUES ('test')"
        is_valid, error = validate_readonly_sql(sql)

        assert is_valid is False
        assert "INSERT" in error
        assert "read-only" in error

    def test_reject_update(self):
        """Test UPDATE statement is rejected"""
        sql = "UPDATE households SET snap_benefit = 0"
        is_valid, error = validate_readonly_sql(sql)

        assert is_valid is False
        assert "UPDATE" in error

    def test_reject_delete(self):
        """Test DELETE statement is rejected"""
        sql = "DELETE FROM households WHERE fiscal_year = 2020"
        is_valid, error = validate_readonly_sql(sql)

        assert is_valid is False
        assert "DELETE" in error

    def test_reject_drop(self):
        """Test DROP statement is rejected"""
        sql = "DROP TABLE households"
        is_valid, error = validate_readonly_sql(sql)

        assert is_valid is False
        assert "DROP" in error

    def test_reject_alter(self):
        """Test ALTER statement is rejected"""
        sql = "ALTER TABLE households ADD COLUMN test TEXT"
        is_valid, error = validate_readonly_sql(sql)

        assert is_valid is False
        assert "ALTER" in error

    def test_reject_create(self):
        """Test CREATE statement is rejected"""
        sql = "CREATE TABLE malicious (id INT)"
        is_valid, error = validate_readonly_sql(sql)

        assert is_valid is False
        assert "CREATE" in error

    def test_reject_truncate(self):
        """Test TRUNCATE statement is rejected"""
        sql = "TRUNCATE TABLE households"
        is_valid, error = validate_readonly_sql(sql)

        assert is_valid is False
        assert "TRUNCATE" in error

    def test_reject_grant(self):
        """Test GRANT statement is rejected"""
        sql = "GRANT ALL ON households TO malicious_user"
        is_valid, error = validate_readonly_sql(sql)

        assert is_valid is False
        assert "GRANT" in error

    def test_reject_revoke(self):
        """Test REVOKE statement is rejected"""
        sql = "REVOKE ALL ON households FROM user"
        is_valid, error = validate_readonly_sql(sql)

        assert is_valid is False
        assert "REVOKE" in error

    def test_reject_exec(self):
        """Test EXEC/EXECUTE statement is rejected"""
        sql = "EXEC sp_malicious_procedure"
        is_valid, error = validate_readonly_sql(sql)

        assert is_valid is False
        assert "EXEC" in error

    def test_case_insensitive_validation(self):
        """Test validation is case-insensitive"""
        sql = "insert INTO households (case_id) VALUES ('test')"
        is_valid, error = validate_readonly_sql(sql)

        assert is_valid is False

        sql = "InSeRt InTo households (case_id) VALUES ('test')"
        is_valid, error = validate_readonly_sql(sql)

        assert is_valid is False

    def test_keyword_in_string_literal(self):
        """Test that keywords in string literals are still detected"""
        # This is a known limitation - we detect the keyword even in strings
        # This is acceptable as it errs on the side of security
        sql = "SELECT 'INSERT INTO' as example FROM households"
        is_valid, error = validate_readonly_sql(sql)

        # Current behavior: rejects because INSERT is in the SQL
        assert is_valid is False

    def test_keyword_in_comment(self):
        """Test that keywords in comments are still detected"""
        sql = """
        SELECT * FROM households
        -- INSERT INTO households VALUES ('test')
        WHERE fiscal_year = 2023
        """
        is_valid, error = validate_readonly_sql(sql)

        # Current behavior: rejects because INSERT is in the SQL
        assert is_valid is False

    def test_sql_injection_attempt(self):
        """Test SQL injection attempts are rejected"""
        sql = "SELECT * FROM households WHERE 1=1; DROP TABLE households"
        is_valid, error = validate_readonly_sql(sql)

        assert is_valid is False
        assert "DROP" in error


class TestSQLValidatorEdgeCases:
    """Test edge cases in SQL validation"""

    def test_empty_sql(self):
        """Test validation of empty SQL"""
        is_valid, error = validate_readonly_sql("")

        assert is_valid is True  # Empty SQL is technically "read-only"

    def test_whitespace_only_sql(self):
        """Test validation of whitespace-only SQL"""
        is_valid, error = validate_readonly_sql("   \n\t  ")

        assert is_valid is True

    def test_very_long_sql(self):
        """Test validation of very long SQL query"""
        sql = "SELECT " + ", ".join([f"col{i}" for i in range(1000)]) + " FROM households"
        is_valid, error = validate_readonly_sql(sql)

        assert is_valid is True

    def test_multiline_sql(self):
        """Test validation of multiline SQL"""
        sql = """
        SELECT
            state_name,
            fiscal_year,
            COUNT(*) as count
        FROM
            households
        WHERE
            fiscal_year >= 2021
        GROUP BY
            state_name,
            fiscal_year
        ORDER BY
            state_name,
            fiscal_year
        """
        is_valid, error = validate_readonly_sql(sql)

        assert is_valid is True

    def test_select_with_subquery(self):
        """Test validation of SELECT with subquery"""
        sql = """
        SELECT * FROM (
            SELECT state_name, snap_benefit
            FROM households
            WHERE fiscal_year = 2023
        ) AS subquery
        WHERE snap_benefit > 500
        """
        is_valid, error = validate_readonly_sql(sql)

        assert is_valid is True
