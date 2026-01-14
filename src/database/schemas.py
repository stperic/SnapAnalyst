"""
SnapAnalyst Pydantic Schemas

Data validation and serialization schemas for API requests/responses.
"""
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

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
    state_code: Optional[str] = None
    state_name: Optional[str] = None
    snap_benefit: Optional[Decimal] = None
    gross_income: Optional[Decimal] = None
    net_income: Optional[Decimal] = None


class HouseholdCreate(HouseholdBase):
    """Schema for creating a household"""
    pass


class HouseholdResponse(HouseholdBase):
    """Schema for household API responses"""
    year_month: Optional[str] = None
    certified_household_size: Optional[int] = None
    num_children: Optional[int] = None
    num_elderly: Optional[int] = None
    created_at: datetime


# Member Schemas
class HouseholdMemberBase(BaseSchema):
    """Base member schema"""
    case_id: str
    fiscal_year: int
    member_number: int = Field(ge=1, le=17)
    age: Optional[int] = Field(None, ge=0, le=120)
    sex: Optional[int] = None
    wages: Decimal = Field(default=0)
    social_security: Decimal = Field(default=0)
    ssi: Decimal = Field(default=0)


class HouseholdMemberCreate(HouseholdMemberBase):
    """Schema for creating a household member"""
    pass


class HouseholdMemberResponse(HouseholdMemberBase):
    """Schema for member API responses"""
    snap_affiliation_code: Optional[int] = None
    total_income: Optional[Decimal] = None
    created_at: datetime


# QC Error Schemas
class QCErrorBase(BaseSchema):
    """Base QC error schema"""
    case_id: str
    fiscal_year: int
    error_number: int = Field(ge=1, le=9)
    element_code: Optional[int] = None
    nature_code: Optional[int] = None
    error_amount: Optional[Decimal] = None


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
    rows_loaded: Optional[int] = None
    households_created: Optional[int] = None
    members_created: Optional[int] = None
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[int] = None


# API Request/Response Schemas
class LoadRequest(BaseModel):
    """Schema for data load API request"""
    fiscal_year: int = Field(..., ge=2000, le=2100)
    filename: Optional[str] = None
    skip_validation: bool = False
    batch_size: int = Field(default=1000, ge=100, le=10000)
    truncate_existing: bool = False


class LoadResponse(BaseModel):
    """Schema for data load API response"""
    status: str
    job_id: str
    message: str
    fiscal_year: int
    estimated_time_seconds: Optional[int] = None
    progress_url: Optional[str] = None


class LoadStatusResponse(BaseModel):
    """Schema for load status API response"""
    job_id: str
    status: str  # queued, in_progress, completed, failed
    progress: Optional[dict] = None
    started_at: Optional[datetime] = None
    elapsed_seconds: Optional[int] = None
    estimated_remaining_seconds: Optional[int] = None
    error_message: Optional[str] = None


class FileInfoResponse(BaseModel):
    """Schema for file information"""
    filename: str
    fiscal_year: int
    size_mb: float
    last_modified: Optional[datetime] = None
    loaded: bool
    loaded_at: Optional[datetime] = None
    row_count: Optional[int] = None


class FilesListResponse(BaseModel):
    """Schema for files list API response"""
    files: List[FileInfoResponse]


class ResetRequest(BaseModel):
    """Schema for database reset request"""
    confirm: bool = Field(..., description="Must be true to confirm reset")
    fiscal_years: Optional[List[int]] = Field(None, description="Specific years to reset")
    backup: bool = Field(default=True, description="Create backup before reset")


class ResetResponse(BaseModel):
    """Schema for database reset response"""
    status: str
    message: str
    backup_file: Optional[str] = None
    deleted: dict


class HealthResponse(BaseModel):
    """Schema for health check response"""
    status: str
    database: dict
    tables: Optional[dict] = None
