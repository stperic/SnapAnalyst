"""
Simplified pytest configuration - no database required for basic tests
"""
from pathlib import Path

import pytest

# Test data directory
TEST_DATA_DIR = Path(__file__).parent.parent / "data"


@pytest.fixture
def test_csv_path() -> Path:
    """Path to test CSV file - skips test if file doesn't exist"""
    csv_path = TEST_DATA_DIR / "test.csv"
    if not csv_path.exists():
        pytest.skip(f"Test data file not found: {csv_path}. Run locally with test data to execute these tests.")
    return csv_path


@pytest.fixture
def fiscal_year() -> int:
    """Default fiscal year for testing"""
    return 2023
