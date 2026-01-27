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
if not os.environ.get('OMP_NUM_THREADS') or os.environ.get('OMP_NUM_THREADS') == '0':
    os.environ['OMP_NUM_THREADS'] = '4'
if not os.environ.get('ORT_DISABLE_CPU_EP_AFFINITY'):
    os.environ['ORT_DISABLE_CPU_EP_AFFINITY'] = '1'
if not os.environ.get('ORT_DISABLE_THREAD_AFFINITY'):
    os.environ['ORT_DISABLE_THREAD_AFFINITY'] = '1'
if not os.environ.get('OMP_WAIT_POLICY'):
    os.environ['OMP_WAIT_POLICY'] = 'PASSIVE'
if not os.environ.get('OMP_PROC_BIND'):
    os.environ['OMP_PROC_BIND'] = 'false'

import subprocess
import sys
import time
import zipfile
from pathlib import Path

# Add project root to path
sys.path.insert(0, '/app')

# Configuration
DATA_DIR = Path(os.environ.get('SNAPDATA_PATH', '/data'))
DATABASE_URL = os.environ.get('DATABASE_URL')

# Available fiscal years and their download URLs
# Data source: https://snapqcdata.net/data
DATA_FILES = {
    2023: {
        'zip_filename': 'qcfy2023_csv.zip',
        'csv_pattern': 'qc_pub_fy2023*.csv',  # Pattern to match extracted CSV
        'url': 'https://snapqcdata.net/sites/default/files/2025-03/qcfy2023_csv.zip'
    },
    2022: {
        'zip_filename': 'qcfy2022_csv.zip',
        'csv_pattern': 'qc_pub_fy2022*.csv',
        'url': 'https://snapqcdata.net/sites/default/files/2024-05/qcfy2022_csv.zip'
    },
    2021: {
        'zip_filename': 'qcfy2021_csv.zip',
        'csv_pattern': 'qc_pub_fy2021*.csv',
        'url': 'https://snapqcdata.net/sites/default/files/2024-05/qcfy2021_csv.zip'
    },
}


def wait_for_database(max_retries=30, delay=2):
    """Wait for PostgreSQL to be ready."""
    print("Waiting for PostgreSQL to be ready...")

    from sqlalchemy import create_engine, text

    for attempt in range(max_retries):
        try:
            engine = create_engine(DATABASE_URL)
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            print("PostgreSQL is ready!")
            return True
        except Exception:
            print(f"  Attempt {attempt + 1}/{max_retries}: Database not ready yet...")
            time.sleep(delay)

    print("ERROR: Could not connect to PostgreSQL after maximum retries")
    return False


def download_and_extract_file(year: int, file_info: dict) -> tuple[bool, str]:
    """
    Download a ZIP file and extract CSV if it doesn't exist.
    Returns (success: bool, csv_filename: str)
    """
    zip_filepath = DATA_DIR / file_info['zip_filename']

    # Check if CSV already exists
    existing_csvs = list(DATA_DIR.glob(file_info['csv_pattern']))
    if existing_csvs:
        csv_file = existing_csvs[0]
        size_mb = csv_file.stat().st_size / (1024 * 1024)
        if size_mb > 1:  # Valid file (> 1MB)
            print(f"  FY{year}: CSV already exists ({size_mb:.1f} MB)")
            return True, csv_file.name
        else:
            print(f"  FY{year}: Existing CSV too small, removing...")
            csv_file.unlink()

    # Download ZIP if not exists
    if not zip_filepath.exists():
        print(f"  FY{year}: Downloading ZIP from snapqcdata.net...")
        print(f"          URL: {file_info['url']}")
        try:
            # Note: snapqcdata.net requires a User-Agent header
            subprocess.run(
                ['curl', '-L', '-A', 'Mozilla/5.0', '-f', '--progress-bar', '-o', str(zip_filepath), file_info['url']],
                capture_output=False,
                check=True
            )

            if not zip_filepath.exists():
                print(f"  FY{year}: Download failed")
                return False, None

            size_mb = zip_filepath.stat().st_size / (1024 * 1024)
            if size_mb < 1:
                print(f"  FY{year}: WARNING - ZIP file too small ({size_mb:.2f} MB)")
                print("          The URL may have changed. Check:")
                print("          https://snapqcdata.net/data")
                zip_filepath.unlink()
                return False, None
            print(f"  FY{year}: Downloaded ZIP successfully ({size_mb:.1f} MB)")
        except subprocess.CalledProcessError:
            print(f"  FY{year}: Download failed (URL may have changed)")
            print("          Check: https://snapqcdata.net/data")
            if zip_filepath.exists():
                zip_filepath.unlink()
            return False, None

    # Extract ZIP
    print(f"  FY{year}: Extracting ZIP file...")
    try:
        with zipfile.ZipFile(zip_filepath, 'r') as zip_ref:
            # List all files in ZIP
            zip_contents = zip_ref.namelist()
            csv_files = [f for f in zip_contents if f.endswith('.csv') and not f.startswith('__MACOSX')]

            if not csv_files:
                print(f"  FY{year}: ERROR - No CSV files found in ZIP")
                return False, None

            # Extract CSV files
            for csv_file in csv_files:
                zip_ref.extract(csv_file, DATA_DIR)
                extracted_path = DATA_DIR / csv_file
                if extracted_path.exists():
                    size_mb = extracted_path.stat().st_size / (1024 * 1024)
                    print(f"  FY{year}: Extracted {csv_file} ({size_mb:.1f} MB)")

        # Remove ZIP file to save space
        print(f"  FY{year}: Removing ZIP file to save space...")
        zip_filepath.unlink()

        # Find the extracted CSV
        existing_csvs = list(DATA_DIR.glob(file_info['csv_pattern']))
        if existing_csvs:
            return True, existing_csvs[0].name
        else:
            print(f"  FY{year}: ERROR - Expected CSV file not found after extraction")
            return False, None

    except Exception as e:
        print(f"  FY{year}: Extraction failed - {e}")
        if zip_filepath.exists():
            zip_filepath.unlink()
        return False, None


def check_data_loaded(year: int) -> bool:
    """Check if data for a fiscal year is already in the database."""
    try:
        from sqlalchemy import create_engine, text
        engine = create_engine(DATABASE_URL)

        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT COUNT(*) FROM households WHERE fiscal_year = :year"),
                {"year": year}
            )
            count = result.scalar()
            return count > 0
    except Exception:
        return False


def load_data_file(year: int, filename: str) -> bool:
    """Load a CSV file into the database using the ETL pipeline."""
    print(f"  FY{year}: Loading into database...")
    print("          This may take several minutes for large files...")

    try:
        from src.etl.loader import ETLLoader

        # Load the data using ETL pipeline
        filepath = DATA_DIR / filename
        loader = ETLLoader(fiscal_year=year)
        status = loader.load_from_file(str(filepath))

        if status.status == 'completed':
            print(f"  FY{year}: Loaded successfully!")
            print(f"          - Households: {status.households_created:,}")
            print(f"          - Members: {status.members_created:,}")
            print(f"          - QC Errors: {status.errors_created:,}")
            return True
        else:
            print(f"  FY{year}: Load failed - {status.error_message}")
            return False

    except Exception as e:
        print(f"  FY{year}: Load failed - {e}")
        import traceback
        traceback.print_exc()
        return False


def train_ai_model():
    """
    Initialize the AI model by pre-loading the Vanna agent.

    The agent learns from:
    1. DDL with embedded COMMENT ON statements from schema.sql
    2. Successful queries saved to ChromaDB agent memory over time
    """
    print()
    print("Step 4: Initializing AI model...")
    print("-" * 40)

    try:
        from src.core.config import settings

        # Check if LLM is configured
        if not settings.openai_api_key and not settings.anthropic_api_key:
            print("  No LLM API keys configured")
            print("  Skipping AI initialization (will happen on first query)")
            return

        print(f"  LLM Provider: {settings.llm_provider}")
        print(f"  SQL Model: {settings.sql_model}")
        print("  Pre-loading Vanna agent...")

        start_time = time.time()

        # Pre-load agent (initializes ChromaDB, downloads ONNX model if needed)
        from src.services.llm_providers import create_agent
        create_agent("snap_qc")

        elapsed = time.time() - start_time
        print(f"  ✓ Agent initialized in {elapsed:.1f} seconds")
        print("  ✓ Schema comments from schema.sql provide example queries")
        print("  ✓ Agent memory learns from successful queries over time")
        print("  ✓ AI model is ready!")

    except Exception as e:
        print(f"  WARNING: AI initialization failed - {e}")
        print("  AI will initialize on first query instead")
        import traceback
        traceback.print_exc()


def main():
    """Main initialization routine."""
    print("=" * 60)
    print("  SnapAnalyst Data Initialization")
    print("=" * 60)
    print()

    # Ensure data directory exists
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Wait for database
    if not wait_for_database():
        sys.exit(1)

    print()
    print("Step 1: Downloading and extracting data files...")
    print("-" * 40)

    available_files = []
    for year, file_info in sorted(DATA_FILES.items()):
        success, csv_filename = download_and_extract_file(year, file_info)
        if success and csv_filename:
            available_files.append((year, csv_filename))

    if not available_files:
        print()
        print("WARNING: No data files available.")
        print("You can manually download data from:")
        print("  https://snapqcdata.net/data")
        print()
        print("Place CSV files in the data volume and restart.")
        print("Continuing with empty database...")
        # Don't exit - let the app start with empty database
        return

    print()
    print("Step 2: Initializing database schema...")
    print("-" * 40)

    try:
        from src.database.init_database import initialize_database
        print("  Creating tables and populating reference data...")
        initialize_database()
        print("  ✓ Database schema initialized!")
    except Exception as e:
        print(f"  ERROR: Database initialization failed - {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    print()
    print("Step 3: Loading data into database...")
    print("-" * 40)

    loaded_count = 0
    skipped_count = 0

    for year, filename in available_files:
        # Check if already loaded
        if check_data_loaded(year):
            print(f"  FY{year}: Already loaded in database, skipping...")
            skipped_count += 1
            continue

        if load_data_file(year, filename):
            loaded_count += 1

    # Initialize AI model
    train_ai_model()

    print()
    print("=" * 60)
    print("  Initialization Complete!")
    print("=" * 60)
    print(f"  Files available: {len(available_files)}")
    print(f"  Years loaded: {loaded_count}")
    print(f"  Years skipped (already loaded): {skipped_count}")
    print()
    print("  Database is ready for queries!")
    print("  AI model is trained and ready!")
    print("=" * 60)


if __name__ == "__main__":
    main()
