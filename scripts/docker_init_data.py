#!/usr/bin/env python3
"""
SnapAnalyst Data Initialization Script

This script is run inside Docker to:
1. Download SNAP QC ZIP files from snapqcdata.net (if not present)
2. Extract CSV files from ZIP archives
3. Load all available data files into the PostgreSQL database

Used by docker-compose data-init service for fully automated setup.
"""

# Configure ONNX Runtime before any imports
# CRITICAL: Multiple settings to completely disable CPU affinity in LXC containers
# See: https://github.com/chroma-core/chroma/issues/1420
import os  # noqa: I001 - Must be first to configure ONNX before other imports

if not os.environ.get("OMP_NUM_THREADS") or os.environ.get("OMP_NUM_THREADS") == "0":
    os.environ["OMP_NUM_THREADS"] = "4"
if not os.environ.get("ORT_DISABLE_CPU_EP_AFFINITY"):
    os.environ["ORT_DISABLE_CPU_EP_AFFINITY"] = "1"
if not os.environ.get("ORT_DISABLE_THREAD_AFFINITY"):
    os.environ["ORT_DISABLE_THREAD_AFFINITY"] = "1"
if not os.environ.get("OMP_WAIT_POLICY"):
    os.environ["OMP_WAIT_POLICY"] = "PASSIVE"
if not os.environ.get("OMP_PROC_BIND"):
    os.environ["OMP_PROC_BIND"] = "false"

import logging
import subprocess
import sys
import time
import zipfile
from pathlib import Path

import yaml

# Suppress noisy library logging in data init script
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
logging.getLogger("src.core.config").setLevel(logging.ERROR)

# Add project root to path
sys.path.insert(0, "/app")

# Configuration
DATA_DIR = Path(os.environ.get("SNAPDATA_PATH", "/data"))
DATABASE_URL = os.environ.get("DATABASE_URL")


def load_data_files_config() -> dict[int, dict[str, str]]:
    """Load data file URLs from config.yaml and derive zip/csv patterns."""
    # Resolve config path: /app/datasets/snap/config.yaml (Docker) or relative
    config_path = Path("/app/datasets/snap/config.yaml")
    if not config_path.exists():
        config_path = Path(__file__).resolve().parent.parent / "datasets" / "snap" / "config.yaml"

    with open(config_path) as f:
        config = yaml.safe_load(f)

    data_files = {}
    for year, url in config.get("data_files", {}).items():
        year = int(year)
        data_files[year] = {
            "zip_filename": f"qcfy{year}_csv.zip",
            "csv_pattern": f"qc_pub_fy{year}*.csv",
            "url": url,
        }
    return data_files


# Available fiscal years and their download URLs (loaded from config.yaml)
DATA_FILES = load_data_files_config()

# Shared engine for all database operations (NullPool = no connection pooling, one-shot use)
_db_engine = None


def _get_engine():
    """Get or create the shared SQLAlchemy engine."""
    global _db_engine
    if _db_engine is None:
        from sqlalchemy import create_engine
        from sqlalchemy.pool import NullPool

        _db_engine = create_engine(DATABASE_URL, poolclass=NullPool)
    return _db_engine


def wait_for_database(max_retries=30, delay=2):
    """Wait for PostgreSQL to be ready. Returns True on success."""
    from sqlalchemy import text

    for attempt in range(max_retries):
        try:
            with _get_engine().connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception:
            if (attempt + 1) % 5 == 0:
                print(f"[init] Waiting for PostgreSQL (attempt {attempt + 1}/{max_retries})...")
            time.sleep(delay)

    return False


def download_and_extract_file(year: int, file_info: dict) -> tuple[bool, str | None, str]:
    """
    Download a ZIP file and extract CSV if it doesn't exist.
    Returns (success, csv_filename, status_description)
    """
    zip_filepath = DATA_DIR / file_info["zip_filename"]

    # Check if CSV already exists
    existing_csvs = list(DATA_DIR.glob(file_info["csv_pattern"]))
    if existing_csvs:
        csv_file = existing_csvs[0]
        size_mb = csv_file.stat().st_size / (1024 * 1024)
        if size_mb > 1:  # Valid file (> 1MB)
            return True, csv_file.name, f"ready ({size_mb:.1f} MB)"
        else:
            csv_file.unlink()

    # Download ZIP if not exists
    if not zip_filepath.exists():
        try:
            # Note: snapqcdata.net requires a User-Agent header
            subprocess.run(
                ["curl", "-L", "-A", "Mozilla/5.0", "-f", "-sS", "-o", str(zip_filepath), file_info["url"]],
                capture_output=False,
                check=True,
            )

            if not zip_filepath.exists():
                return False, None, "download failed"

            size_mb = zip_filepath.stat().st_size / (1024 * 1024)
            if size_mb < 1:
                zip_filepath.unlink()
                return False, None, f"ZIP too small ({size_mb:.2f} MB)"
        except subprocess.CalledProcessError:
            if zip_filepath.exists():
                zip_filepath.unlink()
            return False, None, "download failed"

    # Extract ZIP
    try:
        with zipfile.ZipFile(zip_filepath, "r") as zip_ref:
            zip_contents = zip_ref.namelist()
            csv_files = [f for f in zip_contents if f.endswith(".csv") and not f.startswith("__MACOSX")]

            if not csv_files:
                return False, None, "no CSV in ZIP"

            for csv_file in csv_files:
                zip_ref.extract(csv_file, DATA_DIR)

        zip_filepath.unlink()

        existing_csvs = list(DATA_DIR.glob(file_info["csv_pattern"]))
        if existing_csvs:
            size_mb = existing_csvs[0].stat().st_size / (1024 * 1024)
            return True, existing_csvs[0].name, f"downloaded ({size_mb:.1f} MB)"
        else:
            return False, None, "CSV not found after extraction"

    except Exception as e:
        if zip_filepath.exists():
            zip_filepath.unlink()
        return False, None, f"extraction failed: {e}"


def check_data_loaded(year: int) -> bool:
    """Check if data for a fiscal year is already in the database."""
    try:
        from sqlalchemy import text

        with _get_engine().connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM households WHERE fiscal_year = :year"), {"year": year})
            count = result.scalar()
            return count > 0
    except Exception:
        return False


def load_data_file(year: int, filename: str) -> tuple[bool, str]:
    """Load a CSV file into the database. Returns (success, status_description)."""
    try:
        from src.etl.loader import ETLLoader

        filepath = DATA_DIR / filename
        loader = ETLLoader(fiscal_year=year)
        status = loader.load_from_file(str(filepath))

        if status.status == "completed":
            return True, f"{status.households_created:,} households, {status.members_created:,} members, {status.errors_created:,} errors"
        else:
            return False, f"failed: {status.error_message}"

    except Exception as e:
        return False, f"failed: {e}"


def refresh_materialized_views():
    """Refresh all materialized views after data load. Returns summary string."""
    views = [
        "mv_state_error_rates",
        "mv_error_element_rollup",
        "mv_demographic_profile",
    ]

    failures = []
    try:
        from sqlalchemy import text

        with _get_engine().connect() as conn:
            for view in views:
                try:
                    conn.execute(text(f"REFRESH MATERIALIZED VIEW {view}"))
                    conn.commit()
                except Exception as e:
                    conn.rollback()
                    failures.append(f"{view}: {e}")

        with _get_engine().connect() as conn:
            for table in ["households", "household_members", "qc_errors"] + views:
                try:
                    conn.execute(text(f"ANALYZE {table}"))
                    conn.commit()
                except Exception:
                    conn.rollback()

    except Exception as e:
        failures.append(str(e))

    if failures:
        return f"{len(views) - len(failures)}/{len(views)} refreshed, errors: {'; '.join(failures)}"
    return f"{len(views)} views refreshed + ANALYZE complete"


def train_ai_model() -> str:
    """Initialize the AI model. Returns status description."""
    try:
        from src.core.config import settings

        if not settings.openai_api_key and not settings.anthropic_api_key:
            return "skipped (no API keys, will init on first query)"

        start_time = time.time()

        from src.services.llm_providers import initialize_vanna

        initialize_vanna()

        elapsed = time.time() - start_time
        return f"{settings.llm_provider}/{settings.sql_model} ready ({elapsed:.1f}s)"

    except Exception as e:
        return f"failed: {e} (will retry on first query)"


def download_model_registry() -> str:
    """Download the LiteLLM model registry. Returns status description."""
    try:
        from src.services.model_registry import download_model_registry as _download

        success = _download()
        if success:
            return "ready"
        else:
            return "download failed (will retry on first use)"
    except Exception as e:
        return f"failed: {e}"


def main():
    """Main initialization routine."""
    print("[init] SnapAnalyst Data Initialization starting")

    # Ensure data directory exists
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Wait for database
    if not wait_for_database():
        print("[init] ERROR: Could not connect to PostgreSQL")
        sys.exit(1)
    print("[init] PostgreSQL is ready")

    # Step 1: Download and extract data files
    available_files = []
    file_statuses = []
    for year, file_info in sorted(DATA_FILES.items()):
        success, csv_filename, status = download_and_extract_file(year, file_info)
        file_statuses.append(f"FY{year}: {status}")
        if success and csv_filename:
            available_files.append((year, csv_filename))

    print(f"[init] Step 1 Data files: {', '.join(file_statuses)}")

    if not available_files:
        print("[init] WARNING: No data files available — download from https://snapqcdata.net/data")
        return

    # Step 2: Initialize database schema
    try:
        from src.database.init_database import initialize_database

        initialize_database()
        print("[init] Step 2 Schema initialized")
    except Exception as e:
        print(f"[init] Step 2 ERROR: Schema init failed — {e}")
        sys.exit(1)

    # Step 3: Load data into database
    loaded_count = 0
    skipped_count = 0
    load_statuses = []

    for year, filename in available_files:
        if check_data_loaded(year):
            load_statuses.append(f"FY{year}: exists")
            skipped_count += 1
            continue

        # Data loading can take minutes — print progress before starting
        print(f"[init] Step 3 Loading FY{year}...")
        success, status = load_data_file(year, filename)
        load_statuses.append(f"FY{year}: {status}")
        if success:
            loaded_count += 1

    print(f"[init] Step 3 Data loaded: {', '.join(load_statuses)}")

    # Step 3b: Refresh materialized views after data load
    if loaded_count > 0:
        mv_status = refresh_materialized_views()
        print(f"[init] Step 3b Materialized views: {mv_status}")

    # Step 4: Initialize AI model
    ai_status = train_ai_model()
    print(f"[init] Step 4 AI model: {ai_status}")

    # Step 5: Download model registry
    registry_status = download_model_registry()
    print(f"[init] Step 5 Model registry: {registry_status}")

    print(f"[init] Complete — {len(available_files)} files, {loaded_count} loaded, {skipped_count} skipped")


if __name__ == "__main__":
    main()
