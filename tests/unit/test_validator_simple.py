"""
Unit tests for DataValidator - simplified version
"""
from decimal import Decimal

import pytest

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
