"""
SnapAnalyst Data Validator

Validates data integrity and consistency.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from src.core.logging import get_logger

logger = get_logger(__name__)


class ValidationResult:
    """Result of data validation"""

    def __init__(self):
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.info: list[str] = []

    def add_error(self, message: str) -> None:
        """Add validation error"""
        self.errors.append(message)
        logger.error(f"Validation error: {message}")

    def add_warning(self, message: str) -> None:
        """Add validation warning"""
        self.warnings.append(message)
        logger.warning(f"Validation warning: {message}")

    def add_info(self, message: str) -> None:
        """Add validation info"""
        self.info.append(message)
        logger.info(f"Validation info: {message}")

    @property
    def is_valid(self) -> bool:
        """Check if validation passed (no errors)"""
        return len(self.errors) == 0

    @property
    def has_warnings(self) -> bool:
        """Check if there are warnings"""
        return len(self.warnings) > 0


class DataValidator:
    """Validates SNAP QC data"""

    def __init__(self, strict: bool = True):
        """
        Initialize validator.

        Args:
            strict: If True, treat warnings as errors
        """
        self.strict = strict
        logger.info(f"DataValidator initialized (strict={strict})")

    def validate_household(self, household: dict[str, Any]) -> ValidationResult:
        """
        Validate household record.

        Args:
            household: Household data dict

        Returns:
            ValidationResult
        """
        result = ValidationResult()

        # Required fields
        if not household.get("case_id"):
            result.add_error("Missing case_id")

        if not household.get("fiscal_year"):
            result.add_error("Missing fiscal_year")

        # Numeric validations
        if household.get("snap_benefit") is not None:
            benefit = household["snap_benefit"]
            if isinstance(benefit, (int, float, Decimal)) and benefit < 0:
                result.add_error(f"Negative SNAP benefit: {benefit}")

        if household.get("certified_household_size"):
            size = household["certified_household_size"]
            if size < 1:
                result.add_error(f"Invalid household size: {size}")
            if size > 20:
                result.add_warning(f"Unusually large household: {size}")

        # Logical consistency
        gross = household.get("gross_income")
        net = household.get("net_income")
        if (gross is not None and net is not None
                and isinstance(gross, (int, float, Decimal))
                and isinstance(net, (int, float, Decimal))
                and gross < net):
            result.add_error(f"Gross income ({gross}) < net income ({net})")

        # Income must be non-negative
        for income_field in ["gross_income", "net_income", "earned_income", "unearned_income"]:
            value = household.get(income_field)
            if value is not None and isinstance(value, (int, float, Decimal)) and value < 0:
                result.add_error(f"Negative {income_field}: {value}")

        return result

    def validate_member(self, member: dict[str, Any]) -> ValidationResult:
        """
        Validate household member record.

        Args:
            member: Member data dict

        Returns:
            ValidationResult
        """
        result = ValidationResult()

        # Required fields
        if not member.get("case_id"):
            result.add_error("Missing case_id for member")

        if not member.get("member_number"):
            result.add_error("Missing member_number")

        # Member number range
        member_num = member.get("member_number")
        if member_num and not (1 <= member_num <= 17):
            result.add_error(f"Invalid member_number: {member_num} (must be 1-17)")

        # Age validation
        age = member.get("age")
        if age is not None:
            if not (0 <= age <= 120):
                result.add_error(f"Invalid age: {age} (must be 0-120)")
            if age > 110:
                result.add_warning(f"Unusually high age: {age}")

        # Income fields must be non-negative
        income_fields = [
            "wages", "self_employment_income", "social_security", "ssi",
            "tanf", "unemployment", "child_support", "veterans_benefits"
        ]
        for field in income_fields:
            value = member.get(field)
            if value is not None and isinstance(value, (int, float, Decimal)) and value < 0:
                result.add_error(f"Negative {field}: {value} for member {member_num}")

        return result

    def validate_error(self, error: dict[str, Any]) -> ValidationResult:
        """
        Validate QC error record.

        Args:
            error: Error data dict

        Returns:
            ValidationResult
        """
        result = ValidationResult()

        # Required fields
        if not error.get("case_id"):
            result.add_error("Missing case_id for error")

        if not error.get("error_number"):
            result.add_error("Missing error_number")

        # Error number range
        error_num = error.get("error_number")
        if error_num and not (1 <= error_num <= 9):
            result.add_error(f"Invalid error_number: {error_num} (must be 1-9)")

        # Error amount validation
        amount = error.get("error_amount")
        if amount is not None and isinstance(amount, (int, float, Decimal)):
            if amount < 0:
                result.add_warning(f"Negative error amount: {amount}")
            if amount > 100000:
                result.add_warning(f"Very large error amount: {amount}")

        return result

    def validate_batch(
        self,
        households: list[dict],
        members: list[dict],
        errors: list[dict]
    ) -> ValidationResult:
        """
        Validate entire batch of data.

        Args:
            households: List of household dicts
            members: List of member dicts
            errors: List of error dicts

        Returns:
            ValidationResult
        """
        result = ValidationResult()

        result.add_info(f"Validating batch: {len(households)} households, "
                       f"{len(members)} members, {len(errors)} errors")

        # Validate each household
        for i, household in enumerate(households):
            hh_result = self.validate_household(household)
            if not hh_result.is_valid:
                result.errors.extend([f"Household {i}: {e}" for e in hh_result.errors])
            if hh_result.has_warnings:
                result.warnings.extend([f"Household {i}: {w}" for w in hh_result.warnings])

        # Validate each member
        for i, member in enumerate(members):
            mem_result = self.validate_member(member)
            if not mem_result.is_valid:
                result.errors.extend([f"Member {i}: {e}" for e in mem_result.errors])
            if mem_result.has_warnings:
                result.warnings.extend([f"Member {i}: {w}" for w in mem_result.warnings])

        # Validate each error
        for i, error in enumerate(errors):
            err_result = self.validate_error(error)
            if not err_result.is_valid:
                result.errors.extend([f"Error {i}: {e}" for e in err_result.errors])
            if err_result.has_warnings:
                result.warnings.extend([f"Error {i}: {w}" for w in err_result.warnings])

        return result
