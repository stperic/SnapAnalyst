#!/usr/bin/env python3
"""
SnapAnalyst Data Initialization Script

This script is run inside Docker to:
1. Download SNAP QC CSV files from USDA FNS (if not present)
2. Load all available data files into the PostgreSQL database

Used by docker-compose data-init service for fully automated setup.
"""

import os
import sys
import time
import subprocess
from pathlib import Path

# Add project root to path
sys.path.insert(0, '/app')

# Configuration
DATA_DIR = Path(os.environ.get('SNAPDATA_PATH', '/data'))
DATABASE_URL = os.environ.get('DATABASE_URL')

# Available fiscal years and their download URLs
DATA_FILES = {
    2023: {
        'filename': 'qc_pub_fy2023.csv',
        'url': 'https://www.fns.usda.gov/sites/default/files/resource-files/qc_pub_fy2023.csv'
    },
    2022: {
        'filename': 'qc_pub_fy2022.csv',
        'url': 'https://www.fns.usda.gov/sites/default/files/resource-files/qc_pub_fy2022.csv'
    },
    2021: {
        'filename': 'qc_pub_fy2021.csv',
        'url': 'https://www.fns.usda.gov/sites/default/files/resource-files/qc_pub_fy2021.csv'
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
        except Exception as e:
            print(f"  Attempt {attempt + 1}/{max_retries}: Database not ready yet...")
            time.sleep(delay)
    
    print("ERROR: Could not connect to PostgreSQL after maximum retries")
    return False


def download_file(year: int, file_info: dict) -> bool:
    """Download a data file if it doesn't exist."""
    filepath = DATA_DIR / file_info['filename']
    
    if filepath.exists():
        size_mb = filepath.stat().st_size / (1024 * 1024)
        if size_mb > 1:  # Valid file (> 1MB)
            print(f"  FY{year}: Already exists ({size_mb:.1f} MB)")
            return True
        else:
            print(f"  FY{year}: Existing file too small, removing...")
            filepath.unlink()
    
    print(f"  FY{year}: Downloading from USDA FNS...")
    print(f"          URL: {file_info['url']}")
    try:
        result = subprocess.run(
            ['curl', '-L', '-f', '--progress-bar', '-o', str(filepath), file_info['url']],
            capture_output=False,
            check=True
        )
        
        if filepath.exists():
            size_mb = filepath.stat().st_size / (1024 * 1024)
            if size_mb < 1:
                print(f"  FY{year}: WARNING - File too small ({size_mb:.2f} MB)")
                print(f"          The USDA URL may have changed. Download manually from:")
                print(f"          https://www.fns.usda.gov/snap/quality-control-data")
                filepath.unlink()
                return False
            print(f"  FY{year}: Downloaded successfully ({size_mb:.1f} MB)")
            return True
        return False
    except subprocess.CalledProcessError as e:
        print(f"  FY{year}: Download failed (URL may have changed)")
        print(f"          Download manually from: https://www.fns.usda.gov/snap/quality-control-data")
        if filepath.exists():
            filepath.unlink()
        return False


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
    print(f"          This may take several minutes for large files...")
    
    try:
        from src.database.engine import init_db
        from src.database.init_database import initialize_database
        from src.etl.loader import ETLLoader
        
        # Initialize database tables and reference data
        print(f"  FY{year}: Initializing database schema...")
        initialize_database()
        
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
    print("Step 1: Downloading data files...")
    print("-" * 40)
    
    available_files = []
    for year, file_info in sorted(DATA_FILES.items()):
        filepath = DATA_DIR / file_info['filename']
        if download_file(year, file_info):
            available_files.append((year, file_info['filename']))
        elif filepath.exists() and filepath.stat().st_size > 1024 * 1024:
            # File exists and is valid
            available_files.append((year, file_info['filename']))
    
    if not available_files:
        print()
        print("WARNING: No data files available.")
        print("You can manually download data from:")
        print("  https://www.fns.usda.gov/snap/quality-control-data")
        print()
        print("Place CSV files in the data volume and restart.")
        print("Continuing with empty database...")
        # Don't exit - let the app start with empty database
        return
    
    print()
    print("Step 2: Loading data into database...")
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
    
    print()
    print("=" * 60)
    print("  Initialization Complete!")
    print("=" * 60)
    print(f"  Files available: {len(available_files)}")
    print(f"  Years loaded: {loaded_count}")
    print(f"  Years skipped (already loaded): {skipped_count}")
    print()
    print("  Database is ready for queries!")
    print("=" * 60)


if __name__ == "__main__":
    main()
