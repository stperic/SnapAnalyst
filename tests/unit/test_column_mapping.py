"""
Unit tests for Column Mapping

Tests column name generation and mapping dictionaries.
"""

from src.utils.column_mapping import (
    ERROR_LEVEL_VARIABLES,
    HOUSEHOLD_LEVEL_VARIABLES,
    PERSON_LEVEL_VARIABLES,
    get_all_error_columns,
    get_all_person_columns,
    get_error_column_name,
    get_person_column_name,
    get_required_household_columns,
    get_required_person_columns,
)


class TestGetPersonColumnName:
    """Test get_person_column_name function"""

    def test_member_1(self):
        """Test column name for first member"""
        assert get_person_column_name("WAGES", 1) == "WAGES1"
        assert get_person_column_name("AGE", 1) == "AGE1"
        assert get_person_column_name("SEX", 1) == "SEX1"

    def test_member_17(self):
        """Test column name for last member (17)"""
        assert get_person_column_name("WAGES", 17) == "WAGES17"
        assert get_person_column_name("AGE", 17) == "AGE17"
        assert get_person_column_name("SEX", 17) == "SEX17"

    def test_middle_members(self):
        """Test column names for middle members"""
        assert get_person_column_name("WAGES", 5) == "WAGES5"
        assert get_person_column_name("WAGES", 10) == "WAGES10"

    def test_all_person_variables(self):
        """Test with all person-level variable names"""
        for var in PERSON_LEVEL_VARIABLES:
            result = get_person_column_name(var, 1)
            assert result == f"{var}1"
            assert result.startswith(var)


class TestGetErrorColumnName:
    """Test get_error_column_name function"""

    def test_error_1(self):
        """Test column name for first error"""
        assert get_error_column_name("ELEMENT", 1) == "ELEMENT1"
        assert get_error_column_name("NATURE", 1) == "NATURE1"
        assert get_error_column_name("AMOUNT", 1) == "AMOUNT1"

    def test_error_9(self):
        """Test column name for last error (9)"""
        assert get_error_column_name("ELEMENT", 9) == "ELEMENT9"
        assert get_error_column_name("NATURE", 9) == "NATURE9"
        assert get_error_column_name("AMOUNT", 9) == "AMOUNT9"

    def test_middle_errors(self):
        """Test column names for middle errors"""
        assert get_error_column_name("ELEMENT", 5) == "ELEMENT5"
        assert get_error_column_name("NATURE", 3) == "NATURE3"

    def test_all_error_variables(self):
        """Test with all error-level variable names"""
        for var in ERROR_LEVEL_VARIABLES:
            result = get_error_column_name(var, 1)
            assert result == f"{var}1"
            assert result.startswith(var)


class TestGetAllPersonColumns:
    """Test get_all_person_columns function"""

    def test_returns_list(self):
        """Test function returns a list"""
        result = get_all_person_columns()
        assert isinstance(result, list)

    def test_correct_count(self):
        """Test returns correct number of columns"""
        # Each person variable repeated 17 times
        expected_count = len(PERSON_LEVEL_VARIABLES) * 17
        result = get_all_person_columns()
        assert len(result) == expected_count

    def test_includes_first_member_columns(self):
        """Test includes all first member columns"""
        result = get_all_person_columns()
        assert "WAGES1" in result
        assert "AGE1" in result
        assert "SEX1" in result
        assert "FSAFIL1" in result

    def test_includes_last_member_columns(self):
        """Test includes all last member (17) columns"""
        result = get_all_person_columns()
        assert "WAGES17" in result
        assert "AGE17" in result
        assert "SEX17" in result

    def test_all_variables_represented(self):
        """Test all person variables are represented"""
        result = get_all_person_columns()
        for var in PERSON_LEVEL_VARIABLES:
            # Check at least one member column exists for each variable
            assert any(col.startswith(var) for col in result)


class TestGetAllErrorColumns:
    """Test get_all_error_columns function"""

    def test_returns_list(self):
        """Test function returns a list"""
        result = get_all_error_columns()
        assert isinstance(result, list)

    def test_correct_count(self):
        """Test returns correct number of columns"""
        # Each error variable repeated 9 times
        expected_count = len(ERROR_LEVEL_VARIABLES) * 9
        result = get_all_error_columns()
        assert len(result) == expected_count

    def test_includes_first_error_columns(self):
        """Test includes all first error columns"""
        result = get_all_error_columns()
        assert "ELEMENT1" in result
        assert "NATURE1" in result
        assert "AMOUNT1" in result

    def test_includes_last_error_columns(self):
        """Test includes all last error (9) columns"""
        result = get_all_error_columns()
        assert "ELEMENT9" in result
        assert "NATURE9" in result
        assert "AMOUNT9" in result

    def test_all_variables_represented(self):
        """Test all error variables are represented"""
        result = get_all_error_columns()
        for var in ERROR_LEVEL_VARIABLES:
            # Check at least one error column exists for each variable
            assert any(col.startswith(var) for col in result)


class TestGetRequiredHouseholdColumns:
    """Test get_required_household_columns function"""

    def test_returns_list(self):
        """Test function returns a list"""
        result = get_required_household_columns()
        assert isinstance(result, list)

    def test_includes_case_id(self):
        """Test includes case ID column"""
        result = get_required_household_columns()
        assert "HHLDNO" in result

    def test_includes_state(self):
        """Test includes state column"""
        result = get_required_household_columns()
        assert "STATE" in result

    def test_includes_year_month(self):
        """Test includes year_month column"""
        result = get_required_household_columns()
        assert "YRMONTH" in result

    def test_includes_benefit(self):
        """Test includes SNAP benefit column"""
        result = get_required_household_columns()
        assert "FSBEN" in result

    def test_non_empty(self):
        """Test returns non-empty list"""
        result = get_required_household_columns()
        assert len(result) > 0


class TestGetRequiredPersonColumns:
    """Test get_required_person_columns function"""

    def test_returns_list(self):
        """Test function returns a list"""
        result = get_required_person_columns()
        assert isinstance(result, list)

    def test_includes_affiliation(self):
        """Test includes first member affiliation"""
        result = get_required_person_columns()
        assert "FSAFIL1" in result

    def test_includes_age(self):
        """Test includes first member age"""
        result = get_required_person_columns()
        assert "AGE1" in result

    def test_non_empty(self):
        """Test returns non-empty list"""
        result = get_required_person_columns()
        assert len(result) > 0


class TestPersonLevelVariables:
    """Test PERSON_LEVEL_VARIABLES dictionary"""

    def test_is_dict(self):
        """Test is a dictionary"""
        assert isinstance(PERSON_LEVEL_VARIABLES, dict)

    def test_non_empty(self):
        """Test is not empty"""
        assert len(PERSON_LEVEL_VARIABLES) > 0

    def test_includes_demographics(self):
        """Test includes demographic variables"""
        assert "AGE" in PERSON_LEVEL_VARIABLES
        assert "SEX" in PERSON_LEVEL_VARIABLES
        assert "RACETH" in PERSON_LEVEL_VARIABLES

    def test_includes_income_variables(self):
        """Test includes income variables"""
        assert "WAGES" in PERSON_LEVEL_VARIABLES
        assert "SOCSEC" in PERSON_LEVEL_VARIABLES
        assert "SSI" in PERSON_LEVEL_VARIABLES
        assert "UNEMP" in PERSON_LEVEL_VARIABLES

    def test_all_values_are_strings(self):
        """Test all mapped values are strings"""
        for value in PERSON_LEVEL_VARIABLES.values():
            assert isinstance(value, str)

    def test_all_keys_are_strings(self):
        """Test all keys are strings"""
        for key in PERSON_LEVEL_VARIABLES:
            assert isinstance(key, str)


class TestErrorLevelVariables:
    """Test ERROR_LEVEL_VARIABLES dictionary"""

    def test_is_dict(self):
        """Test is a dictionary"""
        assert isinstance(ERROR_LEVEL_VARIABLES, dict)

    def test_non_empty(self):
        """Test is not empty"""
        assert len(ERROR_LEVEL_VARIABLES) > 0

    def test_includes_element(self):
        """Test includes element code"""
        assert "ELEMENT" in ERROR_LEVEL_VARIABLES

    def test_includes_nature(self):
        """Test includes nature code"""
        assert "NATURE" in ERROR_LEVEL_VARIABLES

    def test_includes_amount(self):
        """Test includes error amount"""
        assert "AMOUNT" in ERROR_LEVEL_VARIABLES

    def test_correct_count(self):
        """Test has correct number of error variables"""
        # Should have 9 error-level variables based on the module
        assert len(ERROR_LEVEL_VARIABLES) == 9

    def test_all_values_are_strings(self):
        """Test all mapped values are strings"""
        for value in ERROR_LEVEL_VARIABLES.values():
            assert isinstance(value, str)


class TestHouseholdLevelVariables:
    """Test HOUSEHOLD_LEVEL_VARIABLES dictionary"""

    def test_is_dict(self):
        """Test is a dictionary"""
        assert isinstance(HOUSEHOLD_LEVEL_VARIABLES, dict)

    def test_non_empty(self):
        """Test is not empty"""
        assert len(HOUSEHOLD_LEVEL_VARIABLES) > 0

    def test_includes_case_id(self):
        """Test includes case ID"""
        assert "HHLDNO" in HOUSEHOLD_LEVEL_VARIABLES
        assert HOUSEHOLD_LEVEL_VARIABLES["HHLDNO"] == "case_id"

    def test_includes_geographic(self):
        """Test includes geographic variables"""
        assert "STATE" in HOUSEHOLD_LEVEL_VARIABLES
        assert "STATENAME" in HOUSEHOLD_LEVEL_VARIABLES
        assert "REGIONCD" in HOUSEHOLD_LEVEL_VARIABLES

    def test_includes_financial(self):
        """Test includes financial variables"""
        assert "RAWGROSS" in HOUSEHOLD_LEVEL_VARIABLES
        assert "RAWNET" in HOUSEHOLD_LEVEL_VARIABLES
        assert "FSBEN" in HOUSEHOLD_LEVEL_VARIABLES

    def test_includes_composition(self):
        """Test includes household composition variables"""
        assert "CERTHHSZ" in HOUSEHOLD_LEVEL_VARIABLES
        assert "FSELDER" in HOUSEHOLD_LEVEL_VARIABLES
        assert "FSKID" in HOUSEHOLD_LEVEL_VARIABLES

    def test_includes_weights(self):
        """Test includes statistical weights"""
        assert "HWGT" in HOUSEHOLD_LEVEL_VARIABLES
        assert "FYWGT" in HOUSEHOLD_LEVEL_VARIABLES

    def test_all_values_are_strings(self):
        """Test all mapped values are strings"""
        for value in HOUSEHOLD_LEVEL_VARIABLES.values():
            assert isinstance(value, str)


class TestColumnMappingIntegration:
    """Integration tests for column mapping functions"""

    def test_no_duplicate_person_columns(self):
        """Test that get_all_person_columns has no duplicates"""
        result = get_all_person_columns()
        assert len(result) == len(set(result))

    def test_no_duplicate_error_columns(self):
        """Test that get_all_error_columns has no duplicates"""
        result = get_all_error_columns()
        assert len(result) == len(set(result))

    def test_required_household_are_in_household_vars(self):
        """Test that required household columns exist in household variables"""
        required = get_required_household_columns()
        for col in required:
            assert col in HOUSEHOLD_LEVEL_VARIABLES

    def test_required_person_follow_naming_convention(self):
        """Test that required person columns follow naming convention"""
        required = get_required_person_columns()
        for col in required:
            # Should end with a digit
            assert col[-1].isdigit()
            # Should have a base variable name
            base = col[:-1]
            assert base in PERSON_LEVEL_VARIABLES

    def test_person_and_error_columns_dont_overlap(self):
        """Test that person and error columns don't overlap"""
        person_cols = set(get_all_person_columns())
        error_cols = set(get_all_error_columns())
        overlap = person_cols & error_cols
        assert len(overlap) == 0, f"Found overlapping columns: {overlap}"
