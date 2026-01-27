"""
Multi-Dataset Architecture

This package provides infrastructure for managing multiple datasets with
different schemas, each with its own:
- Database schema (PostgreSQL namespace)
- SQLAlchemy models
- ETL transformers and column mappings
- Reference/lookup tables
- Vanna training data (DDL, examples, business context)

ARCHITECTURE:
- Each dataset lives in its own subdirectory (e.g., datasets/snap/)
- A DatasetConfig class describes the dataset's structure
- The DatasetRegistry discovers and manages available datasets
- The application can switch between datasets or query across them

MINIMAL INVASIVE DESIGN:
- Existing code paths work unchanged (default to 'snap' dataset)
- New dataset support is additive, not breaking
- Backward compatible with all existing functionality

Usage:
    from datasets import get_registry, get_dataset

    # List available datasets
    registry = get_registry()
    print(registry.list_datasets())

    # Get specific dataset
    snap = get_dataset('snap')
    print(snap.schema_name)
"""

from datasets.registry import (
    DatasetRegistry,
    get_active_dataset,
    get_dataset,
    get_registry,
    list_datasets,
    set_active_dataset,
)

__all__ = [
    "DatasetRegistry",
    "get_registry",
    "get_dataset",
    "get_active_dataset",
    "set_active_dataset",
    "list_datasets",
]
