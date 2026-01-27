"""
SnapAnalyst Statistics Service

Provides statistical analysis and aggregation functions.
"""
from typing import Any

from sqlalchemy import and_, case, func
from sqlalchemy.orm import Session

from src.core.logging import get_logger
from src.database.engine import SessionLocal
from src.database.models import Household, HouseholdMember, QCError

logger = get_logger(__name__)


class StatisticsService:
    """Service for calculating statistics and aggregations"""

    def __init__(self, session: Session | None = None):
        """
        Initialize statistics service.

        Args:
            session: SQLAlchemy session (optional, will create if not provided)
        """
        self.session = session
        self._own_session = session is None

        if self._own_session:
            self.session = SessionLocal()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._own_session and self.session:
            self.session.close()

    def get_overview_statistics(
        self,
        fiscal_years: list[int] | None = None,
        states: list[str] | None = None
    ) -> dict[str, Any]:
        """
        Get overview statistics across households.

        Args:
            fiscal_years: List of fiscal years to include
            states: List of state codes to include

        Returns:
            Dictionary with overview statistics
        """
        try:
            # Build base query
            query = self.session.query(Household)

            # Apply filters
            if fiscal_years:
                query = query.filter(Household.fiscal_year.in_(fiscal_years))
            if states:
                query = query.filter(Household.state_code.in_(states))

            # Calculate summary statistics
            summary = self.session.query(
                func.count(Household.id).label('total_households'),
                func.sum(Household.snap_benefit).label('total_benefits'),
                func.avg(Household.snap_benefit).label('avg_benefit'),
                func.avg(Household.certified_household_size).label('avg_household_size'),
                func.sum(case((Household.num_elderly > 0, 1), else_=0)).label('households_with_elderly'),
                func.sum(case((Household.num_children > 0, 1), else_=0)).label('households_with_children'),
                func.sum(case((Household.num_disabled > 0, 1), else_=0)).label('households_with_disabled'),
            )

            # Apply same filters to summary
            if fiscal_years:
                summary = summary.filter(Household.fiscal_year.in_(fiscal_years))
            if states:
                summary = summary.filter(Household.state_code.in_(states))

            result = summary.first()

            # Get member count
            member_query = self.session.query(func.count(HouseholdMember.id))
            if fiscal_years or states:
                member_query = member_query.join(Household)
                if fiscal_years:
                    member_query = member_query.filter(Household.fiscal_year.in_(fiscal_years))
                if states:
                    member_query = member_query.filter(Household.state_code.in_(states))

            total_members = member_query.scalar() or 0

            # Format results
            return {
                "total_households": result.total_households or 0,
                "total_members": total_members,
                "total_snap_benefits": float(result.total_benefits or 0),
                "average_benefit_per_household": float(result.avg_benefit or 0),
                "average_household_size": float(result.avg_household_size or 0),
                "households_with_elderly": result.households_with_elderly or 0,
                "households_with_children": result.households_with_children or 0,
                "households_with_disabled": result.households_with_disabled or 0,
            }

        except Exception as e:
            logger.error(f"Error calculating overview statistics: {e}")
            raise

    def get_by_state_statistics(
        self,
        fiscal_years: list[int] | None = None
    ) -> list[dict[str, Any]]:
        """
        Get statistics by state.

        Args:
            fiscal_years: List of fiscal years to include

        Returns:
            List of state statistics
        """
        try:
            query = self.session.query(
                Household.state_code,
                Household.state_name,
                func.count(Household.id).label('household_count'),
                func.sum(Household.snap_benefit).label('total_benefits'),
                func.avg(Household.snap_benefit).label('average_benefit'),
                func.avg(Household.certified_household_size).label('avg_household_size'),
            ).group_by(Household.state_code, Household.state_name)

            if fiscal_years:
                query = query.filter(Household.fiscal_year.in_(fiscal_years))

            results = query.order_by(Household.state_code).all()

            return [
                {
                    "state_code": r.state_code,
                    "state_name": r.state_name,
                    "household_count": r.household_count,
                    "total_benefits": float(r.total_benefits or 0),
                    "average_benefit": float(r.average_benefit or 0),
                    "average_household_size": float(r.avg_household_size or 0),
                }
                for r in results
            ]

        except Exception as e:
            logger.error(f"Error calculating by-state statistics: {e}")
            raise

    def get_income_statistics(
        self,
        fiscal_year: int,
        state: str | None = None
    ) -> dict[str, Any]:
        """
        Get income statistics by source.

        Args:
            fiscal_year: Fiscal year
            state: Optional state code filter

        Returns:
            Income statistics by source
        """
        try:
            # Build base query for members
            query = self.session.query(HouseholdMember).join(Household)
            query = query.filter(Household.fiscal_year == fiscal_year)

            if state:
                query = query.filter(Household.state_code == state)

            # Calculate totals for each income source
            income_sources = {
                "wages": func.sum(HouseholdMember.wages),
                "social_security": func.sum(HouseholdMember.social_security),
                "ssi": func.sum(HouseholdMember.ssi),
                "unemployment": func.sum(HouseholdMember.unemployment),
                "tanf": func.sum(HouseholdMember.tanf),
                "child_support": func.sum(HouseholdMember.child_support),
            }

            income_data = {}
            total_income = 0

            for source_name, source_func in income_sources.items():
                result = query.with_entities(
                    source_func.label('total'),
                    func.count(case((HouseholdMember.__table__.c[source_name] > 0, 1))).label('household_count')
                ).first()

                source_total = float(result.total or 0)
                household_count = result.household_count or 0

                total_income += source_total

                income_data[source_name] = {
                    "total": source_total,
                    "households_with_income": household_count,
                    "average_per_household": source_total / household_count if household_count > 0 else 0,
                }

            # Calculate percentages
            for source_name in income_data:
                source_total = income_data[source_name]["total"]
                income_data[source_name]["percent_of_total"] = (
                    (source_total / total_income * 100) if total_income > 0 else 0
                )

            # Get household count
            household_count = self.session.query(func.count(Household.id)).filter(
                Household.fiscal_year == fiscal_year
            )
            if state:
                household_count = household_count.filter(Household.state_code == state)
            household_count = household_count.scalar()

            return {
                "fiscal_year": fiscal_year,
                "state": state or "all",
                "income_by_source": income_data,
                "total_income": total_income,
                "households_analyzed": household_count,
            }

        except Exception as e:
            logger.error(f"Error calculating income statistics: {e}")
            raise

    def get_demographics_statistics(
        self,
        fiscal_year: int,
        state: str | None = None
    ) -> dict[str, Any]:
        """
        Get demographic statistics.

        Args:
            fiscal_year: Fiscal year
            state: Optional state code filter

        Returns:
            Demographic statistics
        """
        try:
            # Build query
            query = self.session.query(HouseholdMember).join(Household)
            query = query.filter(Household.fiscal_year == fiscal_year)

            if state:
                query = query.filter(Household.state_code == state)

            # Age distribution
            age_dist = query.with_entities(
                func.count(case((HouseholdMember.age.between(0, 17), 1))).label('children'),
                func.count(case((HouseholdMember.age.between(18, 64), 1))).label('adults'),
                func.count(case((HouseholdMember.age >= 65, 1))).label('elderly'),
            ).first()

            # Sex distribution
            sex_dist = query.with_entities(
                func.count(case((HouseholdMember.sex == 1, 1))).label('male'),
                func.count(case((HouseholdMember.sex == 2, 1))).label('female'),
            ).first()

            # Disability and other indicators
            indicators = query.with_entities(
                func.count(case((HouseholdMember.disability_indicator.is_(True), 1))).label('with_disability'),
                func.count(case((HouseholdMember.working_indicator.is_(True), 1))).label('working'),
            ).first()

            total_members = query.count()

            return {
                "fiscal_year": fiscal_year,
                "state": state or "all",
                "demographics": {
                    "age_distribution": {
                        "0-17": age_dist.children or 0,
                        "18-64": age_dist.adults or 0,
                        "65+": age_dist.elderly or 0,
                    },
                    "sex_distribution": {
                        "male": sex_dist.male or 0,
                        "female": sex_dist.female or 0,
                    },
                    "disability_status": {
                        "with_disability": indicators.with_disability or 0,
                        "without_disability": total_members - (indicators.with_disability or 0),
                    },
                    "employment_status": {
                        "working": indicators.working or 0,
                        "not_working": total_members - (indicators.working or 0),
                    },
                },
                "total_members": total_members,
            }

        except Exception as e:
            logger.error(f"Error calculating demographics statistics: {e}")
            raise

    def get_benefits_statistics(
        self,
        fiscal_year: int,
        state: str | None = None
    ) -> dict[str, Any]:
        """
        Get benefit statistics.

        Args:
            fiscal_year: Fiscal year
            state: Optional state code filter

        Returns:
            Benefit statistics
        """
        try:
            query = self.session.query(Household).filter(
                Household.fiscal_year == fiscal_year
            )

            if state:
                query = query.filter(Household.state_code == state)

            # Summary statistics
            summary = query.with_entities(
                func.sum(Household.snap_benefit).label('total_benefits'),
                func.avg(Household.snap_benefit).label('avg_benefit'),
                func.min(Household.snap_benefit).label('min_benefit'),
                func.max(Household.snap_benefit).label('max_benefit'),
                func.count(Household.id).label('households_receiving'),
            ).first()

            # Benefit distribution by range
            distribution = {}
            ranges = [
                (0, 100),
                (101, 200),
                (201, 500),
                (501, 1000),
                (1001, 2000),
                (2001, None),
            ]

            for min_val, max_val in ranges:
                range_query = query
                if max_val is None:
                    range_query = range_query.filter(Household.snap_benefit >= min_val)
                    label = f"{min_val}+"
                else:
                    range_query = range_query.filter(
                        and_(Household.snap_benefit >= min_val, Household.snap_benefit <= max_val)
                    )
                    label = f"{min_val}-{max_val}"

                distribution[label] = range_query.count()

            # By household size
            by_size = self.session.query(
                Household.certified_household_size.label('size'),
                func.count(Household.id).label('households'),
                func.avg(Household.snap_benefit).label('average_benefit'),
                func.sum(Household.snap_benefit).label('total_benefits'),
            ).filter(Household.fiscal_year == fiscal_year)

            if state:
                by_size = by_size.filter(Household.state_code == state)

            by_size = by_size.group_by(Household.certified_household_size).all()

            return {
                "fiscal_year": fiscal_year,
                "state": state or "all",
                "benefits": {
                    "total_benefits_issued": float(summary.total_benefits or 0),
                    "average_benefit": float(summary.avg_benefit or 0),
                    "min_benefit": float(summary.min_benefit or 0),
                    "max_benefit": float(summary.max_benefit or 0),
                    "households_receiving": summary.households_receiving or 0,
                },
                "distribution": distribution,
                "by_household_size": [
                    {
                        "size": r.size,
                        "households": r.households,
                        "average_benefit": float(r.average_benefit or 0),
                        "total_benefits": float(r.total_benefits or 0),
                    }
                    for r in by_size if r.size
                ],
            }

        except Exception as e:
            logger.error(f"Error calculating benefits statistics: {e}")
            raise

    def get_error_statistics(
        self,
        fiscal_year: int,
        state: str | None = None
    ) -> dict[str, Any]:
        """
        Get QC error statistics.

        Args:
            fiscal_year: Fiscal year
            state: Optional state code filter

        Returns:
            Error statistics
        """
        try:
            # Get households for filter
            hh_query = self.session.query(
                Household.case_id,
                Household.fiscal_year
            ).filter(
                Household.fiscal_year == fiscal_year
            )
            if state:
                hh_query = hh_query.filter(Household.state_code == state)

            # Get case IDs for filtering errors
            household_keys = [(hh.case_id, hh.fiscal_year) for hh in hh_query.all()]
            total_households = len(household_keys)

            if total_households == 0:
                return {
                    "fiscal_year": fiscal_year,
                    "state": state or "all",
                    "error_summary": {
                        "total_errors": 0,
                        "households_with_errors": 0,
                        "error_rate_percent": 0,
                        "total_error_amount": 0,
                        "average_error_amount": 0,
                    },
                    "by_error_type": {}
                }

            # Build filter for errors using case_id and fiscal_year
            case_ids = [hh[0] for hh in household_keys]

            # Error summary - filter by case_id and fiscal_year
            error_query = self.session.query(QCError).filter(
                QCError.case_id.in_(case_ids),
                QCError.fiscal_year == fiscal_year
            )

            total_errors = error_query.count()
            households_with_errors = self.session.query(
                func.count(func.distinct(QCError.case_id))
            ).filter(
                QCError.case_id.in_(case_ids),
                QCError.fiscal_year == fiscal_year
            ).scalar()

            total_error_amount = error_query.with_entities(
                func.sum(QCError.error_amount)
            ).scalar() or 0

            avg_error_amount = error_query.with_entities(
                func.avg(QCError.error_amount)
            ).scalar() or 0

            # By error type (element code)
            by_element = self.session.query(
                QCError.element_code,
                func.count().label('count'),
                func.sum(QCError.error_amount).label('total_amount'),
                func.avg(QCError.error_amount).label('average_amount'),
            ).filter(
                QCError.case_id.in_(case_ids),
                QCError.fiscal_year == fiscal_year
            ).group_by(QCError.element_code).all()

            return {
                "fiscal_year": fiscal_year,
                "state": state or "all",
                "error_summary": {
                    "total_errors": total_errors,
                    "households_with_errors": households_with_errors or 0,
                    "error_rate_percent": (households_with_errors / total_households * 100) if total_households > 0 else 0,
                    "total_error_amount": float(total_error_amount),
                    "average_error_amount": float(avg_error_amount),
                },
                "by_error_type": {
                    str(r.element_code): {
                        "count": r.count,
                        "total_amount": float(r.total_amount or 0),
                        "average_amount": float(r.average_amount or 0),
                    }
                    for r in by_element if r.element_code
                },
            }

        except Exception as e:
            logger.error(f"Error calculating error statistics: {e}")
            raise
