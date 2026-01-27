"""
Unit tests for DataTransformer - simplified version
"""
import polars as pl

from src.etl.transformer import DataTransformer


class TestDataTransformer:
    """Test suite for DataTransformer class"""

    def test_init(self, fiscal_year: int):
        """Test DataTransformer initialization"""
        transformer = DataTransformer(fiscal_year)

        assert transformer.fiscal_year == fiscal_year

    def test_extract_households_basic(self, fiscal_year: int):
        """Test basic household extraction"""
        # Create simple test DataFrame
        df = pl.DataFrame({
            "HHLDNO": ["TEST001"],
            "STATE": ["CA"],
            "STATENAME": ["California"],
            "FSBEN": [284.50],
            "RAWGROSS": [2000.00],
            "CERTHHSZ": [2],
        })

        transformer = DataTransformer(fiscal_year)
        households_df = transformer.extract_households(df)

        assert len(households_df) == 1
        assert households_df["case_id"][0] == "TEST001"
        assert households_df["state_code"][0] == "CA"
        assert households_df["fiscal_year"][0] == fiscal_year
        assert households_df["snap_benefit"][0] == 284.50

    def test_extract_households_multiple_rows(self, fiscal_year: int):
        """Test household extraction with multiple rows"""
        df = pl.DataFrame({
            "HHLDNO": ["TEST001", "TEST002", "TEST003"],
            "STATE": ["CA", "TX", "NY"],
            "FSBEN": [284.50, 312.00, 256.75],
        })

        transformer = DataTransformer(fiscal_year)
        households_df = transformer.extract_households(df)

        assert len(households_df) == 3
        assert list(households_df["case_id"]) == ["TEST001", "TEST002", "TEST003"]

    def test_extract_members_single_member(self, fiscal_year: int):
        """Test member extraction with single member household"""
        df = pl.DataFrame({
            "HHLDNO": ["TEST001"],
            "FSAFIL1": [1],
            "AGE1": [35],
            "SEX1": [2],
            "WAGES1": [2000.00],
            "SOCSEC1": [0.00],
            # No FSAFIL2, so only 1 member
        })

        transformer = DataTransformer(fiscal_year)
        members_df = transformer.extract_members_fast(df)

        assert len(members_df) == 1
        assert members_df["case_id"][0] == "TEST001"
        assert members_df["member_number"][0] == 1
        assert members_df["age"][0] == 35

    def test_extract_members_multiple_members(self, fiscal_year: int):
        """Test member extraction with multiple members"""
        df = pl.DataFrame({
            "HHLDNO": ["TEST001"],
            "FSAFIL1": [1],
            "AGE1": [35],
            "WAGES1": [2000.00],
            "FSAFIL2": [1],
            "AGE2": [32],
            "WAGES2": [1500.00],
            "FSAFIL3": [1],
            "AGE3": [8],
            "WAGES3": [0.00],
        })

        transformer = DataTransformer(fiscal_year)
        members_df = transformer.extract_members_fast(df)

        assert len(members_df) == 3
        assert list(members_df["member_number"]) == [1, 2, 3]
        assert list(members_df["age"]) == [35, 32, 8]

    def test_extract_errors_single_error(self, fiscal_year: int):
        """Test error extraction with single error"""
        df = pl.DataFrame({
            "HHLDNO": ["TEST001"],
            "ELEMENT1": [520],
            "NATURE1": [75],
            "AMOUNT1": [100.00],
            # No ELEMENT2, so only 1 error
        })

        transformer = DataTransformer(fiscal_year)
        errors_df = transformer.extract_errors_fast(df)

        assert len(errors_df) == 1
        assert errors_df["case_id"][0] == "TEST001"
        assert errors_df["error_number"][0] == 1
        assert errors_df["element_code"][0] == 520

    def test_extract_errors_multiple_errors(self, fiscal_year: int):
        """Test error extraction with multiple errors"""
        df = pl.DataFrame({
            "HHLDNO": ["TEST001"],
            "ELEMENT1": [520],
            "AMOUNT1": [100.00],
            "ELEMENT2": [363],
            "AMOUNT2": [50.00],
            "ELEMENT3": [520],
            "AMOUNT3": [25.00],
        })

        transformer = DataTransformer(fiscal_year)
        errors_df = transformer.extract_errors_fast(df)

        assert len(errors_df) == 3
        assert list(errors_df["error_number"]) == [1, 2, 3]

    def test_extract_errors_no_errors(self, fiscal_year: int):
        """Test error extraction when no errors exist"""
        df = pl.DataFrame({
            "HHLDNO": ["TEST001"],
            "ELEMENT1": [None],
            "ELEMENT2": [None],
        })

        transformer = DataTransformer(fiscal_year)
        errors_df = transformer.extract_errors_fast(df)

        # Should return empty DataFrame
        assert len(errors_df) == 0

    def test_transform_complete_pipeline(self, fiscal_year: int):
        """Test complete transformation pipeline"""
        df = pl.DataFrame({
            "HHLDNO": ["TEST001", "TEST002"],
            "STATE": ["CA", "TX"],
            "FSBEN": [284.50, 312.00],
            "CERTHHSZ": [2, 3],
            # Member data
            "FSAFIL1": [1, 1],
            "AGE1": [35, 45],
            "WAGES1": [2000.00, 1500.00],
            "FSAFIL2": [1, 1],
            "AGE2": [8, 42],
            "WAGES2": [0.00, 1200.00],
            # Error data
            "ELEMENT1": [520, None],
            "AMOUNT1": [100.00, None],
        })

        transformer = DataTransformer(fiscal_year)
        households_df, members_df, errors_df = transformer.transform(df)

        # Verify households
        assert len(households_df) == 2
        assert list(households_df["case_id"]) == ["TEST001", "TEST002"]

        # Verify members
        assert len(members_df) == 4  # 2 members from each household

        # Verify errors
        assert len(errors_df) == 1  # Only TEST001 has error
        assert errors_df["case_id"][0] == "TEST001"
