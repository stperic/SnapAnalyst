#!/usr/bin/env python3
"""
Run integration tests for SnapAnalyst

This script runs database and API integration tests.
"""

import subprocess
import sys
from pathlib import Path


def run_tests():
    """Run integration tests"""
    project_root = Path(__file__).parent.parent

    print("=" * 80)
    print("SnapAnalyst Integration Tests")
    print("=" * 80)

    # Set PYTHONPATH
    import os

    os.environ["PYTHONPATH"] = str(project_root)

    # Run database integration tests
    print("\n" + "=" * 80)
    print("1. DATABASE INTEGRATION TESTS")
    print("=" * 80)

    result_db = subprocess.run(
        ["pytest", "tests/integration/test_database_integration.py", "-v", "-s", "--tb=short"], cwd=project_root
    )

    # Run API integration tests
    print("\n" + "=" * 80)
    print("2. API INTEGRATION TESTS")
    print("=" * 80)

    result_api = subprocess.run(
        ["pytest", "tests/integration/test_api_integration.py", "-v", "-s", "--tb=short"], cwd=project_root
    )

    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)

    db_status = "✅ PASSED" if result_db.returncode == 0 else "❌ FAILED"
    api_status = "✅ PASSED" if result_api.returncode == 0 else "❌ FAILED"

    print(f"Database Integration Tests: {db_status}")
    print(f"API Integration Tests: {api_status}")

    if result_db.returncode == 0 and result_api.returncode == 0:
        print("\n🎉 ALL INTEGRATION TESTS PASSED!")
        return 0
    else:
        print("\n❌ SOME TESTS FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(run_tests())
