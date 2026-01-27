"""
Unit tests for Filter Manager

Tests DataFilter class for per-user filtering functionality.
"""

from datetime import datetime
from unittest.mock import MagicMock, patch

from src.core.filter_manager import DataFilter, FilterManager, get_filter_manager


class TestDataFilterBasics:
    """Test basic DataFilter functionality"""

    def test_empty_filter(self):
        """Test empty filter creation"""
        filter = DataFilter()

        assert filter.is_empty is True
        assert filter.is_active is False
        assert filter.state is None
        assert filter.fiscal_year is None

    def test_filter_with_state(self):
        """Test filter with single state"""
        filter = DataFilter(states=["Connecticut"])

        assert filter.is_empty is False
        assert filter.is_active is True
        assert filter.state == "Connecticut"
        assert filter.fiscal_year is None

    def test_filter_with_year(self):
        """Test filter with single fiscal year"""
        filter = DataFilter(fiscal_years=[2023])

        assert filter.is_empty is False
        assert filter.is_active is True
        assert filter.state is None
        assert filter.fiscal_year == 2023

    def test_filter_with_both(self):
        """Test filter with both state and year"""
        filter = DataFilter(states=["Maryland"], fiscal_years=[2023])

        assert filter.is_empty is False
        assert filter.is_active is True
        assert filter.state == "Maryland"
        assert filter.fiscal_year == 2023

    def test_filter_with_timestamps(self):
        """Test filter with created/updated timestamps"""
        now = datetime.now()
        filter = DataFilter(
            states=["Texas"],
            created_at=now,
            updated_at=now
        )

        assert filter.created_at == now
        assert filter.updated_at == now


class TestDataFilterMultipleValues:
    """Test future multi-value filter support"""

    def test_multiple_states(self):
        """Test filter with multiple states (future feature)"""
        filter = DataFilter(states=["Connecticut", "Maryland", "Texas"])

        assert filter.is_active is True
        assert filter.state == "Connecticut"  # Returns first for backward compat
        assert len(filter.states) == 3

    def test_multiple_years(self):
        """Test filter with multiple fiscal years (future feature)"""
        filter = DataFilter(fiscal_years=[2021, 2022, 2023])

        assert filter.is_active is True
        assert filter.fiscal_year == 2021  # Returns first for backward compat
        assert len(filter.fiscal_years) == 3


class TestDataFilterSQLConditions:
    """Test SQL condition generation"""

    def test_single_state_condition(self):
        """Test SQL condition for single state"""
        filter = DataFilter(states=["Connecticut"])

        conditions = filter.get_sql_conditions()

        assert len(conditions) == 1
        assert conditions[0] == "state_name = 'Connecticut'"

    def test_single_year_condition(self):
        """Test SQL condition for single year"""
        filter = DataFilter(fiscal_years=[2023])

        conditions = filter.get_sql_conditions()

        assert len(conditions) == 1
        assert conditions[0] == "fiscal_year = 2023"

    def test_both_conditions(self):
        """Test SQL conditions for both state and year"""
        filter = DataFilter(states=["Maryland"], fiscal_years=[2023])

        conditions = filter.get_sql_conditions()

        assert len(conditions) == 2
        assert "state_name = 'Maryland'" in conditions
        assert "fiscal_year = 2023" in conditions

    def test_multiple_states_condition(self):
        """Test SQL condition for multiple states (future)"""
        filter = DataFilter(states=["Connecticut", "Maryland", "Texas"])

        conditions = filter.get_sql_conditions()

        assert len(conditions) == 1
        assert "state_name IN ('Connecticut', 'Maryland', 'Texas')" in conditions[0]

    def test_multiple_years_condition(self):
        """Test SQL condition for multiple years (future)"""
        filter = DataFilter(fiscal_years=[2021, 2022, 2023])

        conditions = filter.get_sql_conditions()

        assert len(conditions) == 1
        assert "fiscal_year IN (2021, 2022, 2023)" in conditions[0]

    def test_empty_filter_conditions(self):
        """Test that empty filter returns no conditions"""
        filter = DataFilter()

        conditions = filter.get_sql_conditions()

        assert len(conditions) == 0


class TestDataFilterDescription:
    """Test human-readable descriptions"""

    def test_empty_filter_description(self):
        """Test description of empty filter"""
        filter = DataFilter()

        description = filter.get_description()

        assert "No filter" in description or "All data" in description

    def test_state_only_description(self):
        """Test description with state only"""
        filter = DataFilter(states=["Connecticut"])

        description = filter.get_description()

        assert "Connecticut" in description
        assert "State:" in description

    def test_year_only_description(self):
        """Test description with year only"""
        filter = DataFilter(fiscal_years=[2023])

        description = filter.get_description()

        assert "2023" in description
        assert "Year:" in description or "FY" in description

    def test_both_description(self):
        """Test description with both state and year"""
        filter = DataFilter(states=["Maryland"], fiscal_years=[2023])

        description = filter.get_description()

        assert "Maryland" in description
        assert "2023" in description

    def test_multiple_states_description(self):
        """Test description with multiple states (future)"""
        filter = DataFilter(states=["Connecticut", "Maryland"])

        description = filter.get_description()

        # Should mention multiple states
        assert "Connecticut" in description
        assert "Maryland" in description


class TestDataFilterToDict:
    """Test dictionary conversion"""

    def test_empty_filter_to_dict(self):
        """Test converting empty filter to dict"""
        filter = DataFilter()

        data = filter.to_dict()

        assert data["state"] is None
        assert data["fiscal_year"] is None
        assert data["states"] == []
        assert data["fiscal_years"] == []
        assert data["is_active"] is False

    def test_filter_with_values_to_dict(self):
        """Test converting filter with values to dict"""
        filter = DataFilter(states=["Connecticut"], fiscal_years=[2023])

        data = filter.to_dict()

        assert data["state"] == "Connecticut"
        assert data["fiscal_year"] == 2023
        assert data["states"] == ["Connecticut"]
        assert data["fiscal_years"] == [2023]
        assert data["is_active"] is True

    def test_filter_with_timestamps_to_dict(self):
        """Test converting filter with timestamps to dict"""
        now = datetime.now()
        filter = DataFilter(states=["Texas"], created_at=now, updated_at=now)

        data = filter.to_dict()

        assert data["created_at"] is not None
        assert data["updated_at"] is not None
        assert isinstance(data["created_at"], str)  # ISO format
        assert isinstance(data["updated_at"], str)

    def test_filter_without_timestamps_to_dict(self):
        """Test converting filter without timestamps to dict"""
        filter = DataFilter(states=["Texas"])

        data = filter.to_dict()

        assert data["created_at"] is None
        assert data["updated_at"] is None


class TestDataFilterEdgeCases:
    """Test edge cases"""

    def test_sql_injection_in_state_name(self):
        """Test handling of SQL injection attempt in state name"""
        # Note: This tests that the filter generates the condition
        # The actual SQL execution should use parameterized queries
        filter = DataFilter(states=["'; DROP TABLE households; --"])

        conditions = filter.get_sql_conditions()

        # Should still generate condition (SQL injection protection is at query execution level)
        assert len(conditions) == 1
        assert "state_name = '" in conditions[0]

    def test_special_characters_in_state(self):
        """Test handling of special characters in state name"""
        filter = DataFilter(states=["O'Brien County"])

        conditions = filter.get_sql_conditions()

        assert len(conditions) == 1
        # Note: Proper SQL escaping should be handled at query execution
        assert "O'Brien County" in conditions[0]

    def test_zero_fiscal_year(self):
        """Test handling of zero fiscal year"""
        filter = DataFilter(fiscal_years=[0])

        assert filter.is_active is True
        assert filter.fiscal_year == 0

        conditions = filter.get_sql_conditions()
        assert "fiscal_year = 0" in conditions[0]

    def test_negative_fiscal_year(self):
        """Test handling of negative fiscal year"""
        filter = DataFilter(fiscal_years=[-1])

        conditions = filter.get_sql_conditions()
        assert "fiscal_year = -1" in conditions[0]

    def test_very_large_fiscal_year(self):
        """Test handling of very large fiscal year"""
        filter = DataFilter(fiscal_years=[9999])

        conditions = filter.get_sql_conditions()
        assert "fiscal_year = 9999" in conditions[0]

    def test_empty_state_string(self):
        """Test handling of empty state string"""
        filter = DataFilter(states=[""])

        assert filter.is_active is True
        assert filter.state == ""

        conditions = filter.get_sql_conditions()
        assert len(conditions) == 1


class TestFilterManagerGetUserID:
    """Test FilterManager user ID retrieval"""

    @patch('src.database.engine.SessionLocal')
    def test_get_user_id_database_fallback(self, mock_session_local):
        """Test falling back to database user when Chainlit unavailable"""
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session

        mock_result = MagicMock()
        mock_row = ("db_user_456",)
        mock_result.fetchone.return_value = mock_row
        mock_session.execute.return_value = mock_result

        manager = FilterManager()
        user_id = manager._get_user_id()

        # Should use database fallback (chainlit not available in tests)
        assert user_id == "db_user_456"
        mock_session.close.assert_called_once()

    @patch('src.database.engine.SessionLocal', side_effect=Exception("DB error"))
    def test_get_user_id_default_fallback(self, mock_session_local):
        """Test falling back to 'default' when DB fails"""
        manager = FilterManager()
        user_id = manager._get_user_id()

        # Should fall back to "default"
        assert user_id == "default"

    @patch('src.database.engine.SessionLocal')
    def test_get_user_id_no_database_user(self, mock_session_local):
        """Test falling back to default when no user in database"""
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session

        mock_result = MagicMock()
        mock_result.fetchone.return_value = None  # No user found
        mock_session.execute.return_value = mock_result

        manager = FilterManager()
        user_id = manager._get_user_id()

        assert user_id == "default"
        mock_session.close.assert_called_once()


class TestFilterManagerGetFilter:
    """Test FilterManager get_filter method"""

    @patch.object(FilterManager, '_get_user_id', return_value="test_user")
    @patch('src.database.engine.SessionLocal')
    def test_get_filter_with_stored_preferences(self, mock_session_local, mock_get_user_id):
        """Test loading filter from database"""
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session

        mock_result = MagicMock()
        mock_row = ({
            'states': ['California'],
            'fiscal_years': [2023],
            'created_at': '2024-01-01T00:00:00',
            'updated_at': '2024-01-02T00:00:00'
        },)
        mock_result.fetchone.return_value = mock_row
        mock_session.execute.return_value = mock_result

        manager = FilterManager()
        filter_obj = manager.get_filter()

        assert filter_obj.states == ['California']
        assert filter_obj.fiscal_years == [2023]
        assert filter_obj.created_at is not None
        mock_session.close.assert_called_once()

    @patch.object(FilterManager, '_get_user_id', return_value="test_user")
    @patch('src.database.engine.SessionLocal')
    def test_get_filter_no_stored_preferences(self, mock_session_local, mock_get_user_id):
        """Test get_filter returns empty filter when no preferences stored"""
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session

        mock_result = MagicMock()
        mock_result.fetchone.return_value = None
        mock_session.execute.return_value = mock_result

        manager = FilterManager()
        filter_obj = manager.get_filter()

        assert filter_obj.is_empty is True
        assert filter_obj.states == []
        assert filter_obj.fiscal_years == []

    @patch.object(FilterManager, '_get_user_id', return_value="test_user")
    @patch('src.database.engine.SessionLocal', side_effect=Exception("DB error"))
    def test_get_filter_database_error(self, mock_session_local, mock_get_user_id):
        """Test get_filter returns empty filter on database error"""
        manager = FilterManager()
        filter_obj = manager.get_filter()

        assert filter_obj.is_empty is True


class TestFilterManagerSetMethods:
    """Test FilterManager set methods"""

    @patch.object(FilterManager, '_save_filter')
    @patch.object(FilterManager, 'get_filter', return_value=DataFilter())
    def test_set_state(self, mock_get_filter, mock_save_filter):
        """Test setting state filter"""
        manager = FilterManager()
        result = manager.set_state("Texas")

        assert result.states == ["Texas"]
        assert result.updated_at is not None
        assert result.created_at is not None
        mock_save_filter.assert_called_once()

    @patch.object(FilterManager, '_save_filter')
    @patch.object(FilterManager, 'get_filter', return_value=DataFilter())
    def test_set_fiscal_year(self, mock_get_filter, mock_save_filter):
        """Test setting fiscal year filter"""
        manager = FilterManager()
        result = manager.set_fiscal_year(2022)

        assert result.fiscal_years == [2022]
        assert result.updated_at is not None
        assert result.created_at is not None
        mock_save_filter.assert_called_once()

    @patch.object(FilterManager, '_save_filter')
    @patch.object(FilterManager, 'get_filter', return_value=DataFilter())
    def test_set_filter_both(self, mock_get_filter, mock_save_filter):
        """Test setting both state and year"""
        manager = FilterManager()
        result = manager.set_filter(state="Virginia", fiscal_year=2021)

        assert result.states == ["Virginia"]
        assert result.fiscal_years == [2021]
        assert result.updated_at is not None
        mock_save_filter.assert_called_once()

    @patch.object(FilterManager, '_save_filter')
    @patch.object(FilterManager, 'get_filter', return_value=DataFilter())
    def test_set_filter_state_only(self, mock_get_filter, mock_save_filter):
        """Test setting only state"""
        manager = FilterManager()
        result = manager.set_filter(state="Florida")

        assert result.states == ["Florida"]
        assert result.fiscal_years == []
        mock_save_filter.assert_called_once()

    @patch.object(FilterManager, '_save_filter')
    def test_clear_filter(self, mock_save_filter):
        """Test clearing all filters"""
        manager = FilterManager()
        result = manager.clear()

        assert result.is_empty is True
        assert result.states == []
        assert result.fiscal_years == []
        mock_save_filter.assert_called_once()


class TestFilterManagerSaveFilter:
    """Test FilterManager _save_filter method"""

    @patch.object(FilterManager, '_get_user_id', return_value="test_user")
    @patch('src.database.engine.SessionLocal')
    def test_save_filter_success(self, mock_session_local, mock_get_user_id):
        """Test saving filter to database"""
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session

        manager = FilterManager()
        filter_obj = DataFilter(states=["Ohio"], fiscal_years=[2020])
        filter_obj.created_at = datetime(2024, 1, 1)
        filter_obj.updated_at = datetime(2024, 1, 2)

        manager._save_filter(filter_obj)

        mock_session.execute.assert_called_once()
        mock_session.commit.assert_called_once()
        mock_session.close.assert_called_once()

    @patch.object(FilterManager, '_get_user_id', return_value="test_user")
    @patch('src.database.engine.SessionLocal', side_effect=Exception("DB error"))
    def test_save_filter_database_error(self, mock_session_local, mock_get_user_id):
        """Test save_filter handles database errors"""
        manager = FilterManager()
        filter_obj = DataFilter(states=["Nevada"])

        # Should not raise exception
        manager._save_filter(filter_obj)


class TestFilterManagerApplyToSQL:
    """Test FilterManager apply_to_sql method"""

    @patch.object(FilterManager, 'get_filter')
    def test_apply_to_sql_empty_filter(self, mock_get_filter):
        """Test apply_to_sql with empty filter returns original SQL"""
        mock_get_filter.return_value = DataFilter()
        manager = FilterManager()

        sql = "SELECT * FROM households"
        result = manager.apply_to_sql(sql)

        assert result == sql

    @patch.object(FilterManager, 'get_filter')
    def test_apply_to_sql_households_state_filter(self, mock_get_filter):
        """Test apply_to_sql with state filter on households"""
        mock_get_filter.return_value = DataFilter(states=["Connecticut"])
        manager = FilterManager()

        sql = "SELECT * FROM households"
        result = manager.apply_to_sql(sql)

        assert "state_name = 'Connecticut'" in result
        assert "WHERE" in result

    @patch.object(FilterManager, 'get_filter')
    def test_apply_to_sql_households_year_filter(self, mock_get_filter):
        """Test apply_to_sql with fiscal year filter"""
        mock_get_filter.return_value = DataFilter(fiscal_years=[2023])
        manager = FilterManager()

        sql = "SELECT * FROM households"
        result = manager.apply_to_sql(sql)

        assert "fiscal_year = 2023" in result
        assert "WHERE" in result

    @patch.object(FilterManager, 'get_filter')
    def test_apply_to_sql_households_both_filters(self, mock_get_filter):
        """Test apply_to_sql with both state and year"""
        mock_get_filter.return_value = DataFilter(states=["Maryland"], fiscal_years=[2022])
        manager = FilterManager()

        sql = "SELECT * FROM households"
        result = manager.apply_to_sql(sql)

        assert "state_name = 'Maryland'" in result
        assert "fiscal_year = 2022" in result
        assert "AND" in result

    @patch.object(FilterManager, 'get_filter')
    def test_apply_to_sql_existing_where_clause(self, mock_get_filter):
        """Test apply_to_sql adds to existing WHERE clause"""
        mock_get_filter.return_value = DataFilter(states=["Texas"])
        manager = FilterManager()

        sql = "SELECT * FROM households WHERE status = 2"
        result = manager.apply_to_sql(sql)

        assert "state_name = 'Texas'" in result
        assert "status = 2" in result
        assert result.count("WHERE") == 1

    @patch.object(FilterManager, 'get_filter')
    def test_apply_to_sql_with_group_by(self, mock_get_filter):
        """Test apply_to_sql inserts WHERE before GROUP BY"""
        mock_get_filter.return_value = DataFilter(fiscal_years=[2021])
        manager = FilterManager()

        sql = "SELECT state_name, COUNT(*) FROM households GROUP BY state_name"
        result = manager.apply_to_sql(sql)

        assert "WHERE fiscal_year = 2021" in result
        assert result.index("WHERE") < result.index("GROUP BY")

    @patch.object(FilterManager, 'get_filter')
    def test_apply_to_sql_with_order_by(self, mock_get_filter):
        """Test apply_to_sql inserts WHERE before ORDER BY"""
        mock_get_filter.return_value = DataFilter(states=["Florida"])
        manager = FilterManager()

        sql = "SELECT * FROM households ORDER BY snap_benefit DESC"
        result = manager.apply_to_sql(sql)

        assert "WHERE" in result
        assert result.index("WHERE") < result.index("ORDER BY")

    @patch.object(FilterManager, 'get_filter')
    def test_apply_to_sql_with_limit(self, mock_get_filter):
        """Test apply_to_sql inserts WHERE before LIMIT"""
        mock_get_filter.return_value = DataFilter(fiscal_years=[2020])
        manager = FilterManager()

        sql = "SELECT * FROM households LIMIT 100"
        result = manager.apply_to_sql(sql)

        assert "WHERE fiscal_year = 2020" in result
        assert result.index("WHERE") < result.index("LIMIT")

    @patch.object(FilterManager, 'get_filter')
    def test_apply_to_sql_qc_errors_state_filter(self, mock_get_filter):
        """Test apply_to_sql uses subquery for qc_errors table"""
        mock_get_filter.return_value = DataFilter(states=["Virginia"])
        manager = FilterManager()

        sql = "SELECT * FROM qc_errors"
        result = manager.apply_to_sql(sql)

        assert "case_id IN (SELECT case_id FROM households WHERE state_name = 'Virginia')" in result

    @patch.object(FilterManager, 'get_filter')
    def test_apply_to_sql_members_state_filter(self, mock_get_filter):
        """Test apply_to_sql uses subquery for household_members table"""
        mock_get_filter.return_value = DataFilter(states=["Ohio"])
        manager = FilterManager()

        sql = "SELECT * FROM household_members"
        result = manager.apply_to_sql(sql)

        assert "case_id IN (SELECT case_id FROM households WHERE state_name = 'Ohio')" in result

    @patch.object(FilterManager, 'get_filter')
    def test_apply_to_sql_multiple_states(self, mock_get_filter):
        """Test apply_to_sql with multiple states"""
        mock_get_filter.return_value = DataFilter(states=["Texas", "California", "New York"])
        manager = FilterManager()

        sql = "SELECT * FROM households"
        result = manager.apply_to_sql(sql)

        assert "state_name IN ('Texas', 'California', 'New York')" in result

    @patch.object(FilterManager, 'get_filter')
    def test_apply_to_sql_multiple_years(self, mock_get_filter):
        """Test apply_to_sql with multiple fiscal years"""
        mock_get_filter.return_value = DataFilter(fiscal_years=[2020, 2021, 2022])
        manager = FilterManager()

        sql = "SELECT * FROM households"
        result = manager.apply_to_sql(sql)

        assert "fiscal_year IN (2020, 2021, 2022)" in result

    @patch.object(FilterManager, 'get_filter')
    def test_apply_to_sql_case_insensitive_keywords(self, mock_get_filter):
        """Test apply_to_sql handles case-insensitive SQL keywords"""
        mock_get_filter.return_value = DataFilter(states=["Idaho"])
        manager = FilterManager()

        sql = "select * from households where status = 1"
        result = manager.apply_to_sql(sql)

        assert "state_name = 'Idaho'" in result
        assert "status = 1" in result


class TestGetFilterManager:
    """Test get_filter_manager function"""

    def test_get_filter_manager_returns_instance(self):
        """Test get_filter_manager returns FilterManager instance"""
        manager = get_filter_manager()
        assert isinstance(manager, FilterManager)

    def test_get_filter_manager_is_singleton(self):
        """Test get_filter_manager returns same instance"""
        manager1 = get_filter_manager()
        manager2 = get_filter_manager()

        assert manager1 is manager2
