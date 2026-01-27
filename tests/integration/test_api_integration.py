"""
API Integration Tests

Tests the FastAPI endpoints with actual database operations.
"""
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.api.main import app
from src.core.config import settings

# Import reference models to ensure they're registered with Base.metadata
from src.database import reference_models  # noqa: F401
from src.database.models import Base, Household


@pytest.fixture(scope="module")
def test_engine():
    """
    Create test database engine.

    Uses pre-existing database with reference tables. Don't drop tables
    as they have dependent views and are shared across test modules.
    """
    engine = create_engine(str(settings.database_url))
    Base.metadata.create_all(engine)
    yield engine
    # Don't drop tables - they have dependent views
    engine.dispose()


@pytest.fixture
def test_session(test_engine):
    """Create test database session"""
    connection = test_engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(test_engine):
    """FastAPI test client - ensures database tables exist"""
    return TestClient(app)


@pytest.fixture
def sample_csv_file(tmp_path):
    """Create a sample CSV file for testing"""
    csv_content = """HHLDNO,STATE,STATENAME,YRMONTH,FSBEN,RAWGROSS,RAWNET,CERTHHSZ,FSUSIZE,HWGT,FYWGT,FSAFIL1,AGE1,SEX1,WAGES1,SOCSEC1,SSI1
API001,CA,California,202410,500.00,2000.00,1500.00,2,2,1.5,1.0,1,35,2,1500.00,0.00,0.00
API002,TX,Texas,202410,750.50,3000.00,2500.00,3,3,1.8,1.0,1,42,1,2000.00,0.00,0.00
API003,NY,New York,202410,1200.00,1500.00,1200.00,4,4,2.1,1.0,1,28,2,1200.00,0.00,0.00"""

    csv_file = tmp_path / "api_test_data.csv"
    csv_file.write_text(csv_content)

    # Create snapdata directory (now in datasets/snap/data/) and copy file
    snapdata_path = Path(settings.snapdata_path)
    snapdata_path.mkdir(parents=True, exist_ok=True)

    # Create test file that matches the fiscal year used in tests (2024)
    dest_file = snapdata_path / "qc_pub_fy2024.csv"
    dest_file.write_text(csv_content)

    yield dest_file

    # Cleanup
    if dest_file.exists():
        dest_file.unlink()


class TestFileEndpoints:
    """Test file discovery endpoints"""

    def test_snapdata_path_configuration(self, client):
        """
        Test that snapdata_path is correctly configured and accessible.

        This test verifies the configuration is correct WITHOUT relying on
        fixtures that create files. It catches issues like:
        - Missing data directory
        - Broken symlinks
        - Incorrect path configuration
        """
        from pathlib import Path

        from src.core.config import settings

        snapdata_path = Path(settings.snapdata_path)

        # Path must exist (directory or symlink)
        assert snapdata_path.exists(), f"snapdata_path does not exist: {snapdata_path}"

        # If symlink, target must exist
        if snapdata_path.is_symlink():
            assert snapdata_path.resolve().exists(), "snapdata symlink target does not exist"

        # Should be a directory
        assert snapdata_path.is_dir(), f"snapdata_path is not a directory: {snapdata_path}"

    def test_list_files(self, client, sample_csv_file):
        """Test GET /api/v1/data/files"""
        response = client.get("/api/v1/data/files")
        assert response.status_code == 200

        data = response.json()
        assert "files" in data
        assert "total_files" in data
        assert isinstance(data["files"], list)

    def test_get_file_info(self, client, sample_csv_file):
        """Test GET /api/v1/data/files/{filename}"""
        response = client.get(f"/api/v1/data/files/{sample_csv_file.name}")

        if response.status_code == 200:
            data = response.json()
            assert data["filename"] == sample_csv_file.name
            assert "size_mb" in data
            assert "fiscal_year" in data


class TestManagementEndpoints:
    """Test database management endpoints"""

    def test_health_check(self, client):
        """Test GET /api/v1/data/health"""
        response = client.get("/api/v1/data/health")
        assert response.status_code in [200, 503]  # May fail if DB not available

        data = response.json()
        assert "status" in data
        assert "database" in data
        assert "tables" in data

    def test_get_statistics(self, client):
        """Test GET /api/v1/data/stats"""
        response = client.get("/api/v1/data/stats")
        assert response.status_code == 200

        data = response.json()
        assert "summary" in data
        assert "by_fiscal_year" in data
        assert "total_households" in data["summary"]

    def test_reset_database_without_confirmation(self, client):
        """Test POST /api/v1/data/reset without confirmation"""
        response = client.post("/api/v1/data/reset", json={
            "confirm": False
        })
        assert response.status_code == 400
        assert "confirm" in response.json()["detail"].lower()

    def test_reset_database_with_confirmation(self, client, test_session):
        """Test POST /api/v1/data/reset with confirmation"""
        # Add some test data first
        test_household = Household(
            case_id="RESET_TEST",
            fiscal_year=2099,
            state_code="CA",
            snap_benefit=100.00
        )
        test_session.add(test_household)
        test_session.commit()

        # Reset database
        response = client.post("/api/v1/data/reset", json={
            "confirm": True,
            "fiscal_years": [2099]
        })

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "deleted" in data


class TestDataLoadingEndpoints:
    """Test data loading endpoints"""

    def test_load_data_file_not_found(self, client):
        """Test POST /api/v1/data/load with non-existent file"""
        response = client.post("/api/v1/data/load", json={
            "fiscal_year": 2029,  # Valid year but file doesn't exist
            "batch_size": 100
        })

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_load_data_success(self, client, sample_csv_file):
        """Test POST /api/v1/data/load with valid file"""
        response = client.post("/api/v1/data/load", json={
            "fiscal_year": 2024,  # Valid year within range
            "filename": sample_csv_file.name,
            "batch_size": 100,
            "skip_validation": False
        })

        assert response.status_code == 202  # Accepted
        data = response.json()
        assert data["status"] == "accepted"
        assert "job_id" in data
        assert "progress_url" in data

        # Check job status
        job_id = data["job_id"]
        time.sleep(0.5)  # Give background task time to start

        status_response = client.get(f"/api/v1/data/load/status/{job_id}")
        if status_response.status_code == 200:
            status_data = status_response.json()
            assert status_data["job_id"] == job_id
            assert "status" in status_data
            assert "progress" in status_data

    def test_list_jobs(self, client):
        """Test GET /api/v1/data/load/jobs"""
        response = client.get("/api/v1/data/load/jobs")
        assert response.status_code == 200

        data = response.json()
        assert "jobs" in data
        assert isinstance(data["jobs"], list)

    def test_load_multiple_years(self, client, sample_csv_file):
        """Test POST /api/v1/data/load-multiple"""
        response = client.post("/api/v1/data/load-multiple", json={
            "fiscal_years": [2024],  # Valid year within range
            "batch_size": 100
        })

        assert response.status_code == 202
        data = response.json()
        assert "job_ids" in data
        assert isinstance(data["job_ids"], list)


class TestAPIErrorHandling:
    """Test API error handling"""

    def test_invalid_fiscal_year(self, client):
        """Test loading with invalid fiscal year"""
        response = client.post("/api/v1/data/load", json={
            "fiscal_year": 1900,  # Too old
            "batch_size": 100
        })

        assert response.status_code in [400, 404, 422]

    def test_invalid_batch_size(self, client):
        """Test loading with invalid batch size"""
        response = client.post("/api/v1/data/load", json={
            "fiscal_year": 2023,
            "batch_size": 50  # Below minimum
        })

        assert response.status_code == 422  # Validation error

    def test_nonexistent_job_status(self, client):
        """Test checking status of non-existent job"""
        response = client.get("/api/v1/data/load/status/fake_job_id")
        assert response.status_code == 404


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
