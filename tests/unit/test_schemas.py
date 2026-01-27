"""
Unit tests for Pydantic Schemas

Tests data validation and serialization for API schemas.
"""
from datetime import datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from src.database.schemas import (
    HouseholdBase,
    HouseholdCreate,
    HouseholdMemberBase,
    HouseholdMemberCreate,
    HouseholdMemberResponse,
    HouseholdResponse,
    LoadRequest,
    LoadResponse,
    QCErrorBase,
    QCErrorCreate,
    QCErrorResponse,
)


class TestHouseholdSchemas:
    """Test household schema validation"""

    def test_household_base_valid(self):
        """Test creating valid household base"""
        household = HouseholdBase(
            case_id="TEST001",
            fiscal_year=2023,
            state_code="CA",
            snap_benefit=Decimal("284.50")
        )

        assert household.case_id == "TEST001"
        assert household.fiscal_year == 2023
        assert household.state_code == "CA"
        assert household.snap_benefit == Decimal("284.50")

    def test_household_base_optional_fields(self):
        """Test household with only required fields"""
        household = HouseholdBase(
            case_id="TEST001",
            fiscal_year=2023
        )

        assert household.case_id == "TEST001"
        assert household.fiscal_year == 2023
        assert household.state_code is None
        assert household.snap_benefit is None

    def test_household_create(self):
        """Test HouseholdCreate schema"""
        household = HouseholdCreate(
            case_id="TEST001",
            fiscal_year=2023,
            gross_income=Decimal("2000.00"),
            net_income=Decimal("1500.00")
        )

        assert household.case_id == "TEST001"
        assert household.gross_income == Decimal("2000.00")

    def test_household_response(self):
        """Test HouseholdResponse with additional fields"""
        now = datetime.now()
        household = HouseholdResponse(
            case_id="TEST001",
            fiscal_year=2023,
            year_month="202301",
            certified_household_size=3,
            num_children=2,
            num_elderly=0,
            created_at=now
        )

        assert household.year_month == "202301"
        assert household.certified_household_size == 3
        assert household.num_children == 2
        assert household.created_at == now


class TestHouseholdMemberSchemas:
    """Test household member schema validation"""

    def test_member_base_valid(self):
        """Test creating valid member"""
        member = HouseholdMemberBase(
            case_id="TEST001",
            fiscal_year=2023,
            member_number=1,
            age=35,
            sex=2,
            wages=Decimal("2000.00")
        )

        assert member.case_id == "TEST001"
        assert member.member_number == 1
        assert member.age == 35
        assert member.wages == Decimal("2000.00")

    def test_member_base_defaults(self):
        """Test member with default income values"""
        member = HouseholdMemberBase(
            case_id="TEST001",
            fiscal_year=2023,
            member_number=1
        )

        assert member.wages == 0
        assert member.social_security == 0
        assert member.ssi == 0

    def test_member_number_validation_min(self):
        """Test member_number must be >= 1"""
        with pytest.raises(ValidationError) as exc_info:
            HouseholdMemberBase(
                case_id="TEST001",
                fiscal_year=2023,
                member_number=0  # Invalid
            )

        assert "member_number" in str(exc_info.value)

    def test_member_number_validation_max(self):
        """Test member_number must be <= 17"""
        with pytest.raises(ValidationError) as exc_info:
            HouseholdMemberBase(
                case_id="TEST001",
                fiscal_year=2023,
                member_number=18  # Invalid
            )

        assert "member_number" in str(exc_info.value)

    def test_member_age_validation_min(self):
        """Test age must be >= 0"""
        with pytest.raises(ValidationError) as exc_info:
            HouseholdMemberBase(
                case_id="TEST001",
                fiscal_year=2023,
                member_number=1,
                age=-1  # Invalid
            )

        assert "age" in str(exc_info.value)

    def test_member_age_validation_max(self):
        """Test age must be <= 120"""
        with pytest.raises(ValidationError) as exc_info:
            HouseholdMemberBase(
                case_id="TEST001",
                fiscal_year=2023,
                member_number=1,
                age=121  # Invalid
            )

        assert "age" in str(exc_info.value)

    def test_member_create(self):
        """Test HouseholdMemberCreate schema"""
        member = HouseholdMemberCreate(
            case_id="TEST001",
            fiscal_year=2023,
            member_number=1,
            age=25
        )

        assert member.case_id == "TEST001"
        assert member.age == 25

    def test_member_response(self):
        """Test HouseholdMemberResponse with created_at"""
        now = datetime.now()
        member = HouseholdMemberResponse(
            case_id="TEST001",
            fiscal_year=2023,
            member_number=1,
            age=35,
            created_at=now
        )

        assert member.member_number == 1
        assert member.created_at == now


class TestQCErrorSchemas:
    """Test QC error schema validation"""

    def test_qc_error_base_valid(self):
        """Test creating valid QC error"""
        error = QCErrorBase(
            case_id="TEST001",
            fiscal_year=2023,
            error_number=1,
            element_code=520,
            nature_code=75,
            error_amount=Decimal("100.00")
        )

        assert error.case_id == "TEST001"
        assert error.error_number == 1
        assert error.element_code == 520
        assert error.error_amount == Decimal("100.00")

    def test_qc_error_base_optional_fields(self):
        """Test QC error with only required fields"""
        error = QCErrorBase(
            case_id="TEST001",
            fiscal_year=2023,
            error_number=1
        )

        assert error.case_id == "TEST001"
        assert error.error_number == 1
        assert error.element_code is None
        assert error.error_amount is None

    def test_qc_error_number_validation_min(self):
        """Test error_number must be >= 1"""
        with pytest.raises(ValidationError) as exc_info:
            QCErrorBase(
                case_id="TEST001",
                fiscal_year=2023,
                error_number=0  # Invalid
            )

        assert "error_number" in str(exc_info.value)

    def test_qc_error_number_validation_max(self):
        """Test error_number must be <= 9"""
        with pytest.raises(ValidationError) as exc_info:
            QCErrorBase(
                case_id="TEST001",
                fiscal_year=2023,
                error_number=10  # Invalid
            )

        assert "error_number" in str(exc_info.value)

    def test_qc_error_create(self):
        """Test QCErrorCreate schema"""
        error = QCErrorCreate(
            case_id="TEST001",
            fiscal_year=2023,
            error_number=1,
            element_code=520
        )

        assert error.error_number == 1
        assert error.element_code == 520

    def test_qc_error_response(self):
        """Test QCErrorResponse with created_at"""
        now = datetime.now()
        error = QCErrorResponse(
            case_id="TEST001",
            fiscal_year=2023,
            error_number=1,
            created_at=now
        )

        assert error.error_number == 1
        assert error.created_at == now


class TestLoadSchemas:
    """Test data load schema validation"""

    def test_load_request_valid(self):
        """Test valid LoadRequest"""
        request = LoadRequest(fiscal_year=2023)

        assert request.fiscal_year == 2023
        assert request.skip_validation is False
        assert request.batch_size == 1000
        assert request.truncate_existing is False

    def test_load_request_with_all_fields(self):
        """Test LoadRequest with all fields"""
        request = LoadRequest(
            fiscal_year=2023,
            filename="data.csv",
            skip_validation=True,
            batch_size=500,
            truncate_existing=True
        )

        assert request.fiscal_year == 2023
        assert request.filename == "data.csv"
        assert request.skip_validation is True
        assert request.batch_size == 500
        assert request.truncate_existing is True

    def test_load_request_year_validation_min(self):
        """Test fiscal_year must be >= 2000"""
        with pytest.raises(ValidationError) as exc_info:
            LoadRequest(fiscal_year=1999)

        assert "fiscal_year" in str(exc_info.value)

    def test_load_request_year_validation_max(self):
        """Test fiscal_year must be <= 2100"""
        with pytest.raises(ValidationError) as exc_info:
            LoadRequest(fiscal_year=2101)

        assert "fiscal_year" in str(exc_info.value)

    def test_load_request_batch_size_validation_min(self):
        """Test batch_size must be >= 100"""
        with pytest.raises(ValidationError) as exc_info:
            LoadRequest(fiscal_year=2023, batch_size=50)

        assert "batch_size" in str(exc_info.value)

    def test_load_request_batch_size_validation_max(self):
        """Test batch_size must be <= 10000"""
        with pytest.raises(ValidationError) as exc_info:
            LoadRequest(fiscal_year=2023, batch_size=20000)

        assert "batch_size" in str(exc_info.value)

    def test_load_response_valid(self):
        """Test valid LoadResponse"""
        response = LoadResponse(
            status="queued",
            job_id="job-123",
            message="Load started",
            fiscal_year=2023
        )

        assert response.status == "queued"
        assert response.job_id == "job-123"
        assert response.message == "Load started"
        assert response.fiscal_year == 2023

    def test_load_response_with_optional_fields(self):
        """Test LoadResponse with all fields"""
        response = LoadResponse(
            status="in_progress",
            job_id="job-123",
            message="Processing",
            fiscal_year=2023,
            estimated_time_seconds=300,
            progress_url="/api/v1/status/job-123"
        )

        assert response.estimated_time_seconds == 300
        assert response.progress_url == "/api/v1/status/job-123"


class TestSchemaValidation:
    """Test schema validation edge cases"""

    def test_household_missing_required_field(self):
        """Test validation error when required field is missing"""
        with pytest.raises(ValidationError) as exc_info:
            HouseholdBase(
                fiscal_year=2023  # Missing case_id
            )

        assert "case_id" in str(exc_info.value)

    def test_member_invalid_type(self):
        """Test validation error with wrong type"""
        with pytest.raises(ValidationError) as exc_info:
            HouseholdMemberBase(
                case_id="TEST001",
                fiscal_year="not_a_number",  # Should be int
                member_number=1
            )

        assert "fiscal_year" in str(exc_info.value)

    def test_decimal_field_conversion(self):
        """Test Decimal fields accept string and float"""
        household = HouseholdBase(
            case_id="TEST001",
            fiscal_year=2023,
            snap_benefit="284.50"  # String should convert
        )

        assert household.snap_benefit == Decimal("284.50")

    def test_from_orm_mode(self):
        """Test from_attributes config works"""
        # Create a mock ORM object
        class MockORM:
            case_id = "TEST001"
            fiscal_year = 2023
            state_code = "CA"

        household = HouseholdBase.model_validate(MockORM())

        assert household.case_id == "TEST001"
        assert household.fiscal_year == 2023
