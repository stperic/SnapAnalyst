"""
Simplified pytest configuration - no database required for basic tests
"""
from pathlib import Path

import pytest

# Test data directory
TEST_DATA_DIR = Path(__file__).parent.parent / "data"


@pytest.fixture
def test_csv_path() -> Path:
    """Path to test CSV file"""
    return TEST_DATA_DIR / "test.csv"


@pytest.fixture
def fiscal_year() -> int:
    """Default fiscal year for testing"""
    return 2023
