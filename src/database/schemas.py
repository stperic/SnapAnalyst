"""
SnapAnalyst Pydantic Schemas

Data validation and serialization schemas for API requests/responses.
"""
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


# Base Configuration
class BaseSchema(BaseModel):
    """Base schema with common configuration"""

    model_config = ConfigDict(from_attributes=True)


# Household Schemas
class HouseholdBase(BaseSchema):
    """Base household schema"""
    case_id: str
    fiscal_year: int
    state_code: str | None = None
    state_name: str | None = None
    snap_benefit: Decimal | None = None
    gross_income: Decimal | None = None
    net_income: Decimal | None = None


class HouseholdCreate(HouseholdBase):
    """Schema for creating a household"""
    pass


class HouseholdResponse(HouseholdBase):
    """Schema for household API responses"""
    year_month: str | None = None
    certified_household_size: int | None = None
    num_children: int | None = None
    num_elderly: int | None = None
    created_at: datetime


# Member Schemas
class HouseholdMemberBase(BaseSchema):
    """Base member schema"""
    case_id: str
    fiscal_year: int
    member_number: int = Field(ge=1, le=17)
    age: int | None = Field(None, ge=0, le=120)
    sex: int | None = None
    wages: Decimal = Field(default=0)
    social_security: Decimal = Field(default=0)
    ssi: Decimal = Field(default=0)


class HouseholdMemberCreate(HouseholdMemberBase):
    """Schema for creating a household member"""
    pass


class HouseholdMemberResponse(HouseholdMemberBase):
    """Schema for member API responses"""
    snap_affiliation_code: int | None = None
    total_income: Decimal | None = None
    created_at: datetime


# QC Error Schemas
class QCErrorBase(BaseSchema):
    """Base QC error schema"""
    case_id: str
    fiscal_year: int
    error_number: int = Field(ge=1, le=9)
    element_code: int | None = None
    nature_code: int | None = None
    error_amount: Decimal | None = None


class QCErrorCreate(QCErrorBase):
    """Schema for creating a QC error"""
    pass


class QCErrorResponse(QCErrorBase):
    """Schema for QC error API responses"""
    created_at: datetime


# Load History Schemas
class DataLoadHistoryResponse(BaseSchema):
    """Schema for load history API responses"""
    id: int
    fiscal_year: int
    filename: str
    load_status: str
    rows_loaded: int | None = None
    households_created: int | None = None
    members_created: int | None = None
    started_at: datetime
    completed_at: datetime | None = None
    duration_seconds: int | None = None


# API Request/Response Schemas
class LoadRequest(BaseModel):
    """Schema for data load API request"""
    fiscal_year: int = Field(..., ge=2000, le=2100)
    filename: str | None = None
    skip_validation: bool = False
    batch_size: int = Field(default=1000, ge=100, le=10000)
    truncate_existing: bool = False


class LoadResponse(BaseModel):
    """Schema for data load API response"""
    status: str
    job_id: str
    message: str
    fiscal_year: int
    estimated_time_seconds: int | None = None
    progress_url: str | None = None


class LoadStatusResponse(BaseModel):
    """Schema for load status API response"""
    job_id: str
    status: str  # queued, in_progress, completed, failed
    progress: dict | None = None
    started_at: datetime | None = None
    elapsed_seconds: int | None = None
    estimated_remaining_seconds: int | None = None
    error_message: str | None = None


class FileInfoResponse(BaseModel):
    """Schema for file information"""
    filename: str
    fiscal_year: int
    size_mb: float
    last_modified: datetime | None = None
    loaded: bool
    loaded_at: datetime | None = None
    row_count: int | None = None


class FilesListResponse(BaseModel):
    """Schema for files list API response"""
    files: list[FileInfoResponse]


class ResetRequest(BaseModel):
    """Schema for database reset request"""
    confirm: bool = Field(..., description="Must be true to confirm reset")
    fiscal_years: list[int] | None = Field(None, description="Specific years to reset")
    backup: bool = Field(default=True, description="Create backup before reset")


class ResetResponse(BaseModel):
    """Schema for database reset response"""
    status: str
    message: str
    backup_file: str | None = None
    deleted: dict


class HealthResponse(BaseModel):
    """Schema for health check response"""
    status: str
    database: dict
    tables: dict | None = None
