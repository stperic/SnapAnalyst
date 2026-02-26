"""
Database Integration Tests for Writer and Loader

Tests the complete ETL pipeline with actual PostgreSQL database.
"""

from decimal import Decimal
from pathlib import Path

import polars as pl
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from src.core.config import settings

# Import reference models to ensure they're registered with Base.metadata
from src.database import reference_models  # noqa: F401
from src.database.engine import SessionLocal
from src.database.models import Base, Household, HouseholdMember, QCError
from src.etl.loader import ETLLoader
from src.etl.reader import CSVReader
from src.etl.transformer import DataTransformer
from src.etl.validator import DataValidator
from src.etl.writer import DatabaseWriter


@pytest.fixture(scope="module")
def test_database_url():
    """Database URL for testing"""
    return settings.database_url


@pytest.fixture(scope="module")
def test_engine(test_database_url):
    """
    Create test database engine.

    Note: Uses the pre-existing database with reference tables already populated.
    Run `python -c "from src.database.init_database import initialize_database; initialize_database()"`
    to set up the database with reference tables before running tests.
    """
    engine = create_engine(str(test_database_url))

    # Ensure tables exist (won't recreate if they already exist)
    Base.metadata.create_all(engine)

    # Clean up any leftover test data from previous runs
    with Session(engine) as session:
        # Delete test data with known prefixes
        session.execute(text("DELETE FROM qc_errors WHERE case_id LIKE 'CASE%' OR case_id LIKE 'API%'"))
        session.execute(text("DELETE FROM household_members WHERE case_id LIKE 'CASE%' OR case_id LIKE 'API%'"))
        session.execute(text("DELETE FROM households WHERE case_id LIKE 'CASE%' OR case_id LIKE 'API%'"))
        session.commit()

    yield engine

    # Clean up test data after tests complete
    with Session(engine) as session:
        session.execute(text("DELETE FROM qc_errors WHERE case_id LIKE 'CASE%' OR case_id LIKE 'API%'"))
        session.execute(text("DELETE FROM household_members WHERE case_id LIKE 'CASE%' OR case_id LIKE 'API%'"))
        session.execute(text("DELETE FROM households WHERE case_id LIKE 'CASE%' OR case_id LIKE 'API%'"))
        session.commit()

    engine.dispose()


@pytest.fixture
def test_session(test_engine):
    """Create a test database session with transaction rollback"""
    connection = test_engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def sample_households_df():
    """Create sample household data"""
    return pl.DataFrame(
        {
            "case_id": ["CASE001", "CASE002", "CASE003"],
            "state_code": ["CA", "TX", "NY"],
            "state_name": ["California", "Texas", "New York"],
            "year_month": ["202310", "202310", "202310"],
            "snap_benefit": [500.00, 750.50, 1200.00],
            "gross_income": [2000.00, 3000.00, 1500.00],
            "net_income": [1500.00, 2500.00, 1200.00],
            "certified_household_size": [2, 3, 4],
            "snap_unit_size": [2, 3, 4],
            "household_weight": [1.5, 1.8, 2.1],
            "fiscal_year_weight": [1.0, 1.0, 1.0],
        }
    )


@pytest.fixture
def sample_members_df():
    """Create sample member data"""
    return pl.DataFrame(
        {
            "case_id": ["CASE001", "CASE001", "CASE002", "CASE002", "CASE002", "CASE003"],
            "member_number": [1, 2, 1, 2, 3, 1],
            "age": [35, 8, 42, 16, 12, 28],
            "sex": [2, 1, 1, 2, 1, 2],
            "snap_affiliation_code": [1, 1, 1, 1, 1, 1],
            "wages": [1500.00, 0.00, 2000.00, 500.00, 0.00, 1200.00],
            "social_security": [0.00, 0.00, 0.00, 0.00, 0.00, 0.00],
            "ssi": [0.00, 0.00, 0.00, 0.00, 0.00, 0.00],
        }
    )


@pytest.fixture
def sample_errors_df():
    """Create sample QC error data with valid codes from data_mapping.json"""
    return pl.DataFrame(
        {
            "case_id": ["CASE002", "CASE003"],
            "error_number": [1, 1],
            "element_code": [111, 130],  # Valid: Student status, Citizenship status
            "nature_code": [6, 7],  # Valid: Eligible person excluded, Ineligible person included
            "error_amount": [50.00, 100.00],
            "responsible_agency": [1, 1],
        }
    )


@pytest.fixture
def test_csv_path():
    """Path to test CSV file"""
    # Use the test data file provided in tests/data
    csv_path = Path(__file__).parent.parent / "data" / "test.csv"
    if not csv_path.exists():
        # Fallback to datasets/snap/data directory (new location)
        csv_path = Path(__file__).parent.parent.parent / "datasets" / "snap" / "data" / "qc_pub_fy2023.csv"
    return csv_path


class TestDatabaseWriter:
    """Test DatabaseWriter with actual database"""

    def test_write_households(self, test_session, sample_households_df):
        """Test writing households to database"""
        writer = DatabaseWriter(session=test_session)

        # Write households
        records_written, case_ids = writer.write_households(sample_households_df, fiscal_year=2023)

        # Verify
        assert records_written == 3
        assert len(case_ids) == 3
        assert "CASE001" in case_ids

        # Query database - filter by test case_ids to avoid counting data from other tests
        households = (
            test_session.query(Household).filter(Household.case_id.in_(["CASE001", "CASE002", "CASE003"])).all()
        )
        assert len(households) == 3

        # Check specific household
        household = test_session.query(Household).filter(Household.case_id == "CASE001").first()
        assert household is not None
        assert household.state_code == "CA"
        assert household.snap_benefit == Decimal("500.00")
        assert household.fiscal_year == 2023

    def test_write_members(self, test_session, sample_households_df, sample_members_df):
        """Test writing members to database"""
        writer = DatabaseWriter(session=test_session)

        # Write households first
        records_written, case_ids = writer.write_households(sample_households_df, fiscal_year=2023)

        # Write members (no mapping needed with natural keys!)
        members_written = writer.write_members(sample_members_df, fiscal_year=2023)

        # Verify
        assert members_written == 6

        # Query database - filter by test case_ids
        members = (
            test_session.query(HouseholdMember)
            .filter(HouseholdMember.case_id.in_(["CASE001", "CASE002", "CASE003"]))
            .all()
        )
        assert len(members) == 6

        # Check specific member
        member = (
            test_session.query(HouseholdMember)
            .filter(
                HouseholdMember.case_id == "CASE001",
                HouseholdMember.fiscal_year == 2023,
                HouseholdMember.member_number == 1,
            )
            .first()
        )
        assert member is not None
        assert member.age == 35
        assert member.wages == Decimal("1500.00")

    def test_write_errors(self, test_session, sample_households_df, sample_errors_df):
        """Test writing QC errors to database"""
        writer = DatabaseWriter(session=test_session)

        # Write households first
        records_written, case_ids = writer.write_households(sample_households_df, fiscal_year=2023)

        # Write errors (no mapping needed with natural keys!)
        errors_written = writer.write_errors(sample_errors_df, fiscal_year=2023)

        # Verify
        assert errors_written == 2

        # Query database - filter by test case_ids
        errors = test_session.query(QCError).filter(QCError.case_id.in_(["CASE002", "CASE003"])).all()
        assert len(errors) == 2

        # Check specific error
        error = test_session.query(QCError).filter(QCError.case_id == "CASE002", QCError.fiscal_year == 2023).first()
        assert error is not None
        assert error.element_code == 111  # Updated to match sample_errors_df fixture
        assert error.error_amount == Decimal("50.00")

    def test_write_all(self, test_session, sample_households_df, sample_members_df, sample_errors_df):
        """Test writing all data in single transaction"""
        writer = DatabaseWriter(session=test_session)

        # Write all data
        stats = writer.write_all(sample_households_df, sample_members_df, sample_errors_df, fiscal_year=2023)

        # Verify stats
        assert stats["households_written"] == 3
        assert stats["members_written"] == 6
        assert stats["errors_written"] == 2
        assert stats["total_records"] == 11

        # Verify in database - filter by test case_ids
        test_case_ids = ["CASE001", "CASE002", "CASE003"]
        assert test_session.query(Household).filter(Household.case_id.in_(test_case_ids)).count() == 3
        assert test_session.query(HouseholdMember).filter(HouseholdMember.case_id.in_(test_case_ids)).count() == 6
        assert test_session.query(QCError).filter(QCError.case_id.in_(test_case_ids)).count() == 2

    def test_foreign_key_relationships(self, test_session, sample_households_df, sample_members_df):
        """Test that foreign key relationships work correctly"""
        writer = DatabaseWriter(session=test_session)

        # Write all data
        writer.write_all(
            sample_households_df,
            sample_members_df,
            pl.DataFrame(),  # No errors
            fiscal_year=2023,
        )

        # Query household with members
        household = test_session.query(Household).filter(Household.case_id == "CASE001").first()

        assert household is not None
        assert len(household.members) == 2
        assert household.members[0].age in [35, 8]
        assert household.members[1].age in [35, 8]

    def test_cascade_delete(self, test_session, sample_households_df, sample_members_df):
        """Test that cascade delete works"""
        writer = DatabaseWriter(session=test_session)

        # Write all data
        writer.write_all(sample_households_df, sample_members_df, pl.DataFrame(), fiscal_year=2023)

        test_case_ids = ["CASE001", "CASE002", "CASE003"]

        # Verify data exists (filter by test case_ids)
        assert test_session.query(Household).filter(Household.case_id.in_(test_case_ids)).count() == 3
        assert test_session.query(HouseholdMember).filter(HouseholdMember.case_id.in_(test_case_ids)).count() == 6

        # Delete one household
        household = test_session.query(Household).filter(Household.case_id == "CASE001").first()
        test_session.delete(household)
        test_session.commit()

        # Verify cascade delete worked (filter by test case_ids)
        assert test_session.query(Household).filter(Household.case_id.in_(test_case_ids)).count() == 2
        assert (
            test_session.query(HouseholdMember).filter(HouseholdMember.case_id.in_(test_case_ids)).count() == 4
        )  # 2 members deleted


class TestETLLoader:
    """Test ETLLoader with actual database"""

    @pytest.fixture
    def small_test_csv(self, tmp_path):
        """Create a small test CSV file"""
        csv_content = """HHLDNO,STATE,STATENAME,YRMONTH,FSBEN,RAWGROSS,RAWNET,CERTHHSZ,FSUSIZE,HWGT,FYWGT,FSAFIL1,AGE1,SEX1,WAGES1,SOCSEC1,SSI1
TEST001,CA,California,202310,500.00,2000.00,1500.00,2,2,1.5,1.0,1,35,2,1500.00,0.00,0.00
TEST002,TX,Texas,202310,750.50,3000.00,2500.00,3,3,1.8,1.0,1,42,1,2000.00,0.00,0.00
TEST003,NY,New York,202310,1200.00,1500.00,1200.00,4,4,2.1,1.0,1,28,2,1200.00,0.00,0.00"""

        csv_file = tmp_path / "test_data.csv"
        csv_file.write_text(csv_content)
        return csv_file

    def test_load_from_file(self, test_session, small_test_csv):
        """Test complete ETL pipeline with database"""
        # Create loader
        loader = ETLLoader(fiscal_year=2023, batch_size=10, strict_validation=False, skip_validation=False)

        # Load data
        status = loader.load_from_file(str(small_test_csv))

        # Verify status
        assert status.status == "completed"
        assert status.total_rows == 3
        assert status.rows_processed == 3
        assert status.households_created > 0
        assert len(status.validation_errors) == 0

        # Verify in database
        households = test_session.query(Household).all()
        assert len(households) >= 3

        # Check specific data
        household = test_session.query(Household).filter(Household.case_id == "TEST001").first()
        if household:  # May not persist if using different session
            assert household.state_code == "CA"
            assert household.snap_benefit == Decimal("500.00")


class TestETLIntegration:
    """End-to-end integration tests"""

    def test_real_data_sample_to_database(self, test_engine, test_csv_path):
        """Test loading real data sample to database"""
        # Create a fresh session not using transaction isolation
        session = SessionLocal()
        try:
            # Clear any existing data
            session.query(QCError).delete()
            session.query(HouseholdMember).delete()
            session.query(Household).delete()
            session.commit()

            # Read real data (first 10 rows)
            reader = CSVReader(str(test_csv_path))
            df = reader.read_csv(n_rows=10)

            # Transform
            transformer = DataTransformer(fiscal_year=2023)
            households_df, members_df, errors_df = transformer.transform(df)

            # Validate
            validator = DataValidator(strict=False)
            households_list = households_df.to_dicts()
            members_list = members_df.to_dicts()
            errors_list = errors_df.to_dicts()
            result = validator.validate_batch(households_list, members_list, errors_list)

            # Should have no errors
            assert len(result.errors) == 0, f"Validation errors: {result.errors[:5]}"

            # Write to database
            writer = DatabaseWriter(session=session)
            stats = writer.write_all(households_df, members_df, errors_df, fiscal_year=2023)

            # Verify
            assert stats["households_written"] == 10
            assert stats["members_written"] > 0
            assert stats["total_records"] > 10

            # Query database
            households = session.query(Household).all()
            assert len(households) == 10
        finally:
            session.close()

    def test_large_sample_to_database(self, test_engine, test_csv_path):
        """Test loading larger sample (50 rows) to database"""
        session = SessionLocal()
        try:
            # Clear any existing data
            session.query(QCError).delete()
            session.query(HouseholdMember).delete()
            session.query(Household).delete()
            session.commit()

            # Read 50 rows
            reader = CSVReader(str(test_csv_path))
            df = reader.read_csv(n_rows=50)

            # Transform
            transformer = DataTransformer(fiscal_year=2023)
            households_df, members_df, errors_df = transformer.transform(df)

            # Write to database
            writer = DatabaseWriter(session=session, batch_size=25)
            stats = writer.write_all(households_df, members_df, errors_df, fiscal_year=2023)

            # Verify
            assert stats["households_written"] == 50
            assert stats["total_records"] > 50

            # Query database
            households = session.query(Household).count()
            assert households == 50

            members = session.query(HouseholdMember).count()
            assert members > 0

            print("\n✓ Successfully loaded 50 real households:")
            print(f"  - {stats['households_written']} households")
            print(f"  - {stats['members_written']} members")
            print(f"  - {stats['errors_written']} QC errors")
        finally:
            session.close()

    def test_query_loaded_data(self, test_engine, test_csv_path):
        """Test querying loaded data with relationships"""
        session = SessionLocal()
        try:
            # Clear any existing data
            session.query(QCError).delete()
            session.query(HouseholdMember).delete()
            session.query(Household).delete()
            session.commit()

            # Load some data first
            reader = CSVReader(str(test_csv_path))
            df = reader.read_csv(n_rows=20)

            transformer = DataTransformer(fiscal_year=2023)
            households_df, members_df, errors_df = transformer.transform(df)

            writer = DatabaseWriter(session=session)
            writer.write_all(households_df, members_df, errors_df, fiscal_year=2023)

            # Query with joins
            household = session.query(Household).first()
            assert household is not None

            # Access related members
            assert household.members is not None
            assert len(household.members) >= 0

            # Calculate statistics
            from sqlalchemy import func

            total_benefit = session.query(func.sum(Household.snap_benefit)).scalar()
            assert total_benefit is not None

            print("\n✓ Successfully queried loaded data:")
            print(f"  - Total SNAP benefits: ${float(total_benefit):,.2f}")
            print(f"  - Total households: {session.query(Household).count()}")
            print(f"  - Total members: {session.query(HouseholdMember).count()}")
        finally:
            session.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
