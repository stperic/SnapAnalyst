"""
Integration test with real SNAP QC data

Tests the complete ETL pipeline with the actual test.csv file (43,777 rows)
"""

from src.etl.reader import CSVReader
from src.etl.transformer import DataTransformer
from src.etl.validator import DataValidator


class TestRealDataETL:
    """Integration tests with real SNAP QC data"""

    def test_read_real_data_sample(self, test_csv_path):
        """Test reading a sample of real data"""
        reader = CSVReader(str(test_csv_path))

        # Read first 100 rows
        df = reader.read_csv(n_rows=100)

        assert len(df) == 100
        assert "CASE" in df.columns
        assert "STATE" in df.columns
        assert "FSBEN" in df.columns

    def test_transform_real_data_sample(self, test_csv_path, fiscal_year):
        """Test transforming a sample of real data"""
        reader = CSVReader(str(test_csv_path))
        transformer = DataTransformer(fiscal_year)

        # Read first 10 rows for faster testing
        df = reader.read_csv(n_rows=10)

        # Transform
        households_df, members_df, errors_df = transformer.transform(df)

        # Verify households
        assert len(households_df) == 10
        assert "case_id" in households_df.columns
        assert "fiscal_year" in households_df.columns
        assert "snap_benefit" in households_df.columns

        # Verify members exist (each household should have at least 1 member)
        assert len(members_df) > 0
        assert "case_id" in members_df.columns
        assert "member_number" in members_df.columns
        assert "age" in members_df.columns

        # Print summary
        print("\n✓ Transformed 10 households:")
        print(f"  - {len(households_df)} households")
        print(f"  - {len(members_df)} members")
        print(f"  - {len(errors_df)} QC errors")

    def test_complete_etl_pipeline_real_data(self, test_csv_path, fiscal_year):
        """Test complete ETL pipeline with real data"""
        reader = CSVReader(str(test_csv_path))
        transformer = DataTransformer(fiscal_year)
        validator = DataValidator(strict=False)  # Use non-strict for real data

        # Process first 50 rows
        df = reader.read_csv(n_rows=50)

        # Transform
        households_df, members_df, errors_df = transformer.transform(df)

        # Validate (convert to list of dicts for validator)
        households_list = households_df.to_dicts()
        members_list = members_df.to_dicts()
        errors_list = errors_df.to_dicts()

        result = validator.validate_batch(households_list, members_list, errors_list)

        # Print validation results
        print("\n✓ ETL Pipeline Results (50 households):")
        print(f"  - Households: {len(households_df)}")
        print(f"  - Members: {len(members_df)}")
        print(f"  - QC Errors: {len(errors_df)}")
        print(f"  - Validation Errors: {len(result.errors)}")
        print(f"  - Validation Warnings: {len(result.warnings)}")

        if result.errors:
            print("\n  First 5 Errors:")
            for error in result.errors[:5]:
                print(f"    - {error}")

        if result.warnings:
            print("\n  First 5 Warnings:")
            for warning in result.warnings[:5]:
                print(f"    - {warning}")

        # Should have processed all data (warnings OK, errors should be minimal)
        assert len(households_df) == 50
        assert len(members_df) > 0

    def test_data_statistics_real_data(self, test_csv_path, fiscal_year):
        """Test data statistics with real data"""
        reader = CSVReader(str(test_csv_path))
        transformer = DataTransformer(fiscal_year)

        # Process first 1000 rows for meaningful statistics
        df = reader.read_csv(n_rows=1000)
        households_df, members_df, errors_df = transformer.transform(df)

        # Calculate statistics
        total_households = len(households_df)
        total_members = len(members_df)
        total_errors = len(errors_df)
        avg_members_per_household = total_members / total_households if total_households > 0 else 0
        error_rate = (total_errors / total_households * 100) if total_households > 0 else 0

        # Print statistics
        print("\n✓ Data Statistics (1,000 households):")
        print(f"  - Total Households: {total_households:,}")
        print(f"  - Total Members: {total_members:,}")
        print(f"  - Avg Members/Household: {avg_members_per_household:.2f}")
        print(f"  - Total QC Errors: {total_errors:,}")
        print(f"  - Error Rate: {error_rate:.1f}%")

        # Verify reasonable statistics
        assert total_households == 1000
        assert 1.0 <= avg_members_per_household <= 10.0  # Reasonable household size range
        assert error_rate <= 50.0  # Error rate should be reasonable

    def test_column_coverage_real_data(self, test_csv_path):
        """Test that we can read all columns from real data"""
        reader = CSVReader(str(test_csv_path))
        columns = reader.get_column_names()

        print("\n✓ CSV Column Analysis:")
        print(f"  - Total Columns: {len(columns)}")

        # Check for key column patterns
        member_cols = [c for c in columns if c.startswith("FSAFIL")]
        error_cols = [c for c in columns if c.startswith("ELEMENT")]

        print(f"  - Member Affiliation Columns: {len(member_cols)}")
        print(f"  - Error Element Columns: {len(error_cols)}")

        # Verify expected column patterns
        assert len(columns) > 800  # Real data has 850+ columns
        assert len(member_cols) >= 16  # At least 16 members
        assert len(error_cols) >= 9  # At least 9 error positions
