"""
Unit tests for DataValidator - simplified version
"""
from decimal import Decimal

from src.etl.validator import DataValidator, ValidationResult


class TestValidationResult:
    """Test ValidationResult class"""

    def test_init(self):
        """Test ValidationResult initialization"""
        result = ValidationResult()

        assert result.errors == []
        assert result.warnings == []
        assert result.info == []
        assert result.is_valid is True
        assert result.has_warnings is False

    def test_add_error(self):
        """Test adding validation error"""
        result = ValidationResult()
        result.add_error("Test error")

        assert len(result.errors) == 1
        assert result.errors[0] == "Test error"
        assert result.is_valid is False

    def test_add_warning(self):
        """Test adding validation warning"""
        result = ValidationResult()
        result.add_warning("Test warning")

        assert len(result.warnings) == 1
        assert result.warnings[0] == "Test warning"
        assert result.has_warnings is True
        assert result.is_valid is True  # Warnings don't affect validity


class TestDataValidator:
    """Test suite for DataValidator class"""

    def test_init(self):
        """Test DataValidator initialization"""
        validator = DataValidator(strict=True)
        assert validator.strict is True

        validator = DataValidator(strict=False)
        assert validator.strict is False

    def test_validate_household_valid(self):
        """Test validating a valid household"""
        validator = DataValidator()
        household = {
            "case_id": "TEST001",
            "fiscal_year": 2023,
            "state_code": "CA",
            "snap_benefit": Decimal("284.50"),
            "gross_income": Decimal("2000.00"),
            "net_income": Decimal("1500.00"),
            "certified_household_size": 3,
        }

        result = validator.validate_household(household)

        assert result.is_valid
        assert len(result.errors) == 0

    def test_validate_household_missing_case_id(self):
        """Test validation fails when case_id is missing"""
        validator = DataValidator()
        household = {
            "fiscal_year": 2023,
            "snap_benefit": Decimal("284.50"),
        }

        result = validator.validate_household(household)

        assert not result.is_valid
        assert any("case_id" in error for error in result.errors)

    def test_validate_household_negative_benefit(self):
        """Test validation fails with negative SNAP benefit"""
        validator = DataValidator()
        household = {
            "case_id": "TEST001",
            "fiscal_year": 2023,
            "snap_benefit": Decimal("-100.00"),
        }

        result = validator.validate_household(household)

        assert not result.is_valid
        assert any("Negative SNAP benefit" in error for error in result.errors)

    def test_validate_household_invalid_size(self):
        """Test validation fails with invalid household size"""
        validator = DataValidator()
        household = {
            "case_id": "TEST001",
            "fiscal_year": 2023,
            "certified_household_size": -1,  # Negative is clearly invalid
        }

        result = validator.validate_household(household)

        assert not result.is_valid
        assert any("Invalid household size" in error for error in result.errors)

    def test_validate_household_gross_less_than_net(self):
        """Test validation fails when gross < net income"""
        validator = DataValidator()
        household = {
            "case_id": "TEST001",
            "fiscal_year": 2023,
            "gross_income": Decimal("1000.00"),
            "net_income": Decimal("2000.00"),
        }

        result = validator.validate_household(household)

        assert not result.is_valid
        assert any("Gross income" in error and "net income" in error for error in result.errors)

    def test_validate_member_valid(self):
        """Test validating a valid member"""
        validator = DataValidator()
        member = {
            "case_id": "TEST001",
            "member_number": 1,
            "age": 35,
            "sex": 2,
            "wages": Decimal("2000.00"),
            "social_security": Decimal("0.00"),
        }

        result = validator.validate_member(member)

        assert result.is_valid
        assert len(result.errors) == 0

    def test_validate_member_invalid_age(self):
        """Test validation fails with invalid age"""
        validator = DataValidator()
        member = {
            "case_id": "TEST001",
            "member_number": 1,
            "age": 150,  # Too old
        }

        result = validator.validate_member(member)

        assert not result.is_valid
        assert any("Invalid age" in error for error in result.errors)

    def test_validate_member_invalid_number(self):
        """Test validation fails with invalid member number"""
        validator = DataValidator()
        member = {
            "case_id": "TEST001",
            "member_number": 18,  # Max is 17
        }

        result = validator.validate_member(member)

        assert not result.is_valid
        assert any("member_number" in error for error in result.errors)

    def test_validate_member_negative_wages(self):
        """Test validation fails with negative wages"""
        validator = DataValidator()
        member = {
            "case_id": "TEST001",
            "member_number": 1,
            "wages": Decimal("-1000.00"),
        }

        result = validator.validate_member(member)

        assert not result.is_valid
        assert any("Negative wages" in error for error in result.errors)

    def test_validate_error_valid(self):
        """Test validating a valid error"""
        validator = DataValidator()
        error = {
            "case_id": "TEST001",
            "error_number": 1,
            "element_code": 520,
            "nature_code": 75,
            "error_amount": Decimal("100.00"),
        }

        result = validator.validate_error(error)

        assert result.is_valid
        assert len(result.errors) == 0

    def test_validate_error_invalid_number(self):
        """Test validation fails with invalid error number"""
        validator = DataValidator()
        error = {
            "case_id": "TEST001",
            "error_number": 10,  # Max is 9
        }

        result = validator.validate_error(error)

        assert not result.is_valid
        assert any("error_number" in error for error in result.errors)

    def test_validate_error_very_large_amount(self):
        """Test validation warns with very large error amount"""
        validator = DataValidator()
        error = {
            "case_id": "TEST001",
            "error_number": 1,
            "error_amount": Decimal("200000.00"),
        }

        result = validator.validate_error(error)

        # Should pass but with warning
        assert result.is_valid
        assert result.has_warnings
        assert any("large error amount" in warning for warning in result.warnings)

    def test_validate_household_missing_fiscal_year(self):
        """Test validation fails when fiscal_year is missing"""
        validator = DataValidator()
        household = {
            "case_id": "TEST001",
            "snap_benefit": Decimal("284.50"),
        }

        result = validator.validate_household(household)

        assert not result.is_valid
        assert any("fiscal_year" in error for error in result.errors)

    def test_validate_household_large_size_warning(self):
        """Test validation warns with very large household"""
        validator = DataValidator()
        household = {
            "case_id": "TEST001",
            "fiscal_year": 2023,
            "certified_household_size": 25,  # > 20 triggers warning
        }

        result = validator.validate_household(household)

        assert result.is_valid  # Valid but with warning
        assert result.has_warnings
        assert any("large household" in warning for warning in result.warnings)

    def test_validate_household_negative_income(self):
        """Test validation fails with negative income fields"""
        validator = DataValidator()
        household = {
            "case_id": "TEST001",
            "fiscal_year": 2023,
            "gross_income": Decimal("-500.00"),
        }

        result = validator.validate_household(household)

        assert not result.is_valid
        assert any("Negative gross_income" in error for error in result.errors)

    def test_validate_member_missing_case_id(self):
        """Test validation fails when member case_id is missing"""
        validator = DataValidator()
        member = {
            "member_number": 1,
            "age": 35,
        }

        result = validator.validate_member(member)

        assert not result.is_valid
        assert any("case_id" in error for error in result.errors)

    def test_validate_member_missing_member_number(self):
        """Test validation fails when member_number is missing"""
        validator = DataValidator()
        member = {
            "case_id": "TEST001",
            "age": 35,
        }

        result = validator.validate_member(member)

        assert not result.is_valid
        assert any("member_number" in error for error in result.errors)

    def test_validate_error_missing_case_id(self):
        """Test validation fails when error case_id is missing"""
        validator = DataValidator()
        error = {
            "error_number": 1,
            "element_code": 520,
        }

        result = validator.validate_error(error)

        assert not result.is_valid
        assert any("case_id" in error for error in result.errors)

    def test_validate_error_missing_error_number(self):
        """Test validation fails when error_number is missing"""
        validator = DataValidator()
        error = {
            "case_id": "TEST001",
            "element_code": 520,
        }

        result = validator.validate_error(error)

        assert not result.is_valid
        assert any("error_number" in error for error in result.errors)

    def test_validate_error_negative_amount_warning(self):
        """Test validation warns with negative error amount"""
        validator = DataValidator()
        error = {
            "case_id": "TEST001",
            "error_number": 1,
            "error_amount": Decimal("-50.00"),
        }

        result = validator.validate_error(error)

        assert result.is_valid  # Valid but with warning
        assert result.has_warnings
        assert any("Negative error amount" in warning for warning in result.warnings)

    def test_add_info(self):
        """Test adding validation info"""
        result = ValidationResult()
        result.add_info("Test info message")

        assert len(result.info) == 1
        assert result.info[0] == "Test info message"
        assert result.is_valid is True


class TestValidateBatch:
    """Test validate_batch functionality"""

    def test_validate_batch_all_valid(self):
        """Test validating batch with all valid data"""
        validator = DataValidator()

        households = [
            {"case_id": "001", "fiscal_year": 2023, "snap_benefit": Decimal("100.00")},
            {"case_id": "002", "fiscal_year": 2023, "snap_benefit": Decimal("200.00")},
        ]
        members = [
            {"case_id": "001", "member_number": 1, "age": 35},
            {"case_id": "002", "member_number": 1, "age": 40},
        ]
        errors = [
            {"case_id": "001", "error_number": 1, "error_amount": Decimal("50.00")},
        ]

        result = validator.validate_batch(households, members, errors)

        assert result.is_valid
        assert len(result.errors) == 0
        assert len(result.info) > 0  # Should have info messages

    def test_validate_batch_with_household_errors(self):
        """Test validate_batch detects household errors"""
        validator = DataValidator()

        households = [
            {"case_id": "001", "fiscal_year": 2023},
            {"fiscal_year": 2023},  # Missing case_id
        ]
        members = []
        errors = []

        result = validator.validate_batch(households, members, errors)

        assert not result.is_valid
        assert any("Household 1" in error and "case_id" in error for error in result.errors)

    def test_validate_batch_with_member_errors(self):
        """Test validate_batch detects member errors"""
        validator = DataValidator()

        households = [{"case_id": "001", "fiscal_year": 2023}]
        members = [
            {"case_id": "001", "member_number": 1, "age": 35},
            {"case_id": "001", "member_number": 1, "age": 150},  # Invalid age
        ]
        errors = []

        result = validator.validate_batch(households, members, errors)

        assert not result.is_valid
        assert any("Member 1" in error and "age" in error for error in result.errors)

    def test_validate_batch_with_error_errors(self):
        """Test validate_batch detects QC error record errors"""
        validator = DataValidator()

        households = [{"case_id": "001", "fiscal_year": 2023}]
        members = []
        errors = [
            {"case_id": "001", "error_number": 1},
            {"case_id": "001", "error_number": 20},  # Invalid error number
        ]

        result = validator.validate_batch(households, members, errors)

        assert not result.is_valid
        assert any("Error 1" in error and "error_number" in error for error in result.errors)

    def test_validate_batch_with_warnings(self):
        """Test validate_batch collects warnings"""
        validator = DataValidator()

        households = [{"case_id": "001", "fiscal_year": 2023, "certified_household_size": 25}]
        members = []
        errors = []

        result = validator.validate_batch(households, members, errors)

        assert result.is_valid  # No errors
        assert result.has_warnings
        assert any("Household 0" in warning and "large household" in warning for warning in result.warnings)

    def test_validate_batch_with_error_warnings(self):
        """Test validate_batch collects warnings from QC errors"""
        validator = DataValidator()

        households = [{"case_id": "001", "fiscal_year": 2023}]
        members = []
        errors = [
            {"case_id": "001", "error_number": 1, "error_amount": Decimal("200000.00")},  # Large error triggers warning
        ]

        result = validator.validate_batch(households, members, errors)

        assert result.is_valid  # No errors
        assert result.has_warnings
        assert any("Error 0" in warning and "large error amount" in warning for warning in result.warnings)
