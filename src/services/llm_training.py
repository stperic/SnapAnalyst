"""
LLM Training Module

Handles training Vanna on database schema, DDL, and example queries.

ARCHITECTURE (Gold Standard):
- DDL is extracted directly from PostgreSQL (single source of truth)
- Business context comes from dataset-specific prompts
- No duplicate DDL maintenance required

MULTI-DATASET SUPPORT:
- Each dataset can provide its own DDL, examples, and business context
- Training can target specific datasets or combine multiple
- Backward compatible with single-dataset (SNAP) usage

This ensures Vanna always trains on the ACTUAL database schema.
"""

import json
from pathlib import Path
from typing import Dict, List, Any, Optional

from src.core.config import settings
from src.core.logging import get_logger
from src.core.prompts import BUSINESS_CONTEXT_DOCUMENTATION

logger = get_logger(__name__)


def load_schema() -> Dict:
    """
    Load database schema documentation from JSON file.
    
    Returns:
        Schema dictionary
        
    Raises:
        FileNotFoundError: If schema file not found
    """
    schema_path = Path(settings.vanna_schema_path)
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema file not found: {schema_path}")
    
    with open(schema_path, 'r') as f:
        schema = json.load(f)
    
    logger.info(f"Loaded schema from {schema_path}")
    return schema


def load_training_examples() -> List[Dict]:
    """
    Load SQL query examples for training from JSON file.
    
    Returns:
        List of example queries
    """
    examples_path = Path(settings.vanna_training_data_path)
    if not examples_path.exists():
        logger.warning(f"Training examples file not found: {examples_path}")
        return []
    
    with open(examples_path, 'r') as f:
        data = json.load(f)
    
    examples = data.get('example_queries', [])
    logger.info(f"Loaded {len(examples)} training examples from {examples_path}")
    return examples


def get_enhanced_ddl_statements(dataset_name: Optional[str] = None) -> List[str]:
    """
    Get DDL statements extracted directly from PostgreSQL.
    
    This is the Gold Standard approach - the database is the single source of truth.
    DDL is queried from information_schema, not maintained in code.
    
    Args:
        dataset_name: Optional dataset name for multi-dataset support
        
    Returns:
        List of DDL statements from actual database schema
    """
    try:
        from src.database.ddl_extractor import get_all_ddl_statements
        ddl_statements = get_all_ddl_statements(
            include_samples=True,
            dataset_name=dataset_name
        )
        logger.info(f"Extracted {len(ddl_statements)} DDL statements from database")
        return ddl_statements
    except Exception as e:
        logger.error(f"Failed to extract DDL from database: {e}")
        logger.warning("Returning empty DDL list - schema training will be skipped")
        return []


def get_business_context_documentation(dataset_name: Optional[str] = None) -> str:
    """
    Get business terminology documentation for LLM training.
    
    MULTI-DATASET: If dataset_name provided, uses that dataset's business context.
    Otherwise uses default SNAP business context (backward compatible).
    
    Args:
        dataset_name: Optional dataset name for dataset-specific context
        
    Returns:
        Documentation string with business terms and common query patterns
    """
    if dataset_name:
        try:
            from datasets import get_dataset
            dataset_config = get_dataset(dataset_name)
            if dataset_config:
                return dataset_config.get_business_context()
        except ImportError:
            logger.debug("datasets module not available, using default context")
    
    return BUSINESS_CONTEXT_DOCUMENTATION


def train_on_basic_schema(vanna_instance, dataset_name: Optional[str] = None) -> None:
    """
    Train Vanna on DDL with embedded business context.
    
    MULTI-DATASET: If dataset_name provided, trains on that dataset's schema.
    Otherwise trains on default (SNAP) schema.
    
    Args:
        vanna_instance: Vanna instance to train
        dataset_name: Optional dataset name for multi-dataset support
    """
    ds_label = f" for dataset '{dataset_name}'" if dataset_name else ""
    logger.info(f"Training Vanna on enhanced schema with business context{ds_label}...")
    
    # Train on each DDL statement
    ddl_statements = get_enhanced_ddl_statements(dataset_name)
    for ddl in ddl_statements:
        vanna_instance.train(ddl=ddl)
    
    # Train on business context
    business_context = get_business_context_documentation(dataset_name)
    vanna_instance.train(documentation=business_context)
    
    logger.info(f"Trained on {len(ddl_statements)} tables with embedded code lookups and business context")


def train_on_dataset(vanna_instance, dataset_name: str) -> None:
    """
    Train Vanna on a specific dataset's schema and examples.
    
    This is the primary function for multi-dataset training.
    It trains on:
    - DDL from the dataset's tables
    - Business context specific to the dataset
    - Query examples from the dataset
    
    Args:
        vanna_instance: Vanna instance to train
        dataset_name: Name of the dataset to train on
    """
    logger.info(f"Training Vanna on dataset: {dataset_name}")
    
    try:
        from datasets import get_dataset
        dataset_config = get_dataset(dataset_name)
        
        if not dataset_config:
            raise ValueError(f"Dataset '{dataset_name}' not found")
        
        # Train on DDL
        ddl_statements = dataset_config.get_ddl_statements()
        for ddl in ddl_statements:
            vanna_instance.train(ddl=ddl)
        logger.info(f"Trained on {len(ddl_statements)} DDL statements")
        
        # Train on business context
        business_context = dataset_config.get_business_context()
        vanna_instance.train(documentation=business_context)
        logger.info("Trained on business context documentation")
        
        # Train on query examples
        examples = dataset_config.load_query_examples()
        trained_count = train_on_examples(vanna_instance, examples)
        logger.info(f"Trained on {trained_count} query examples")
        
    except ImportError:
        logger.warning("datasets module not available, falling back to default training")
        train_on_basic_schema(vanna_instance)


def train_on_all_datasets(vanna_instance) -> Dict[str, int]:
    """
    Train Vanna on all registered datasets.
    
    Useful for enabling cross-dataset queries.
    
    Args:
        vanna_instance: Vanna instance to train
        
    Returns:
        Dict mapping dataset names to number of DDL statements trained
    """
    results = {}
    
    try:
        from datasets import get_registry
        registry = get_registry()
        
        for dataset_name in registry.list_datasets():
            try:
                train_on_dataset(vanna_instance, dataset_name)
                dataset_config = registry.get(dataset_name)
                ddl_count = len(dataset_config.get_ddl_statements()) if dataset_config else 0
                results[dataset_name] = ddl_count
            except Exception as e:
                logger.error(f"Failed to train on dataset '{dataset_name}': {e}")
                results[dataset_name] = 0
        
    except ImportError:
        logger.warning("datasets module not available")
        train_on_basic_schema(vanna_instance)
        results["snap"] = len(get_enhanced_ddl_statements())
    
    return results


def train_on_examples(vanna_instance, examples: List[Dict]) -> int:
    """
    Train Vanna on example queries.
    
    Args:
        vanna_instance: Vanna instance to train
        examples: List of example query dictionaries
        
    Returns:
        Number of examples successfully trained
    """
    logger.info(f"Training Vanna on {len(examples)} query examples...")
    
    trained_count = 0
    for example in examples:
        question = example.get('question')
        sql = example.get('sql')
        
        if question and sql:
            try:
                vanna_instance.train(question=question, sql=sql)
                trained_count += 1
            except Exception as e:
                logger.warning(f"Failed to train on example: {question[:50]}... - {e}")
    
    logger.info(f"Successfully trained on {trained_count} examples")
    return trained_count


def generate_ddl_from_schema(table_name: str, table_info: Dict) -> str:
    """
    Generate DDL statement from schema definition.
    
    Args:
        table_name: Name of the table
        table_info: Table information dictionary
        
    Returns:
        DDL CREATE TABLE statement
    """
    columns = []
    for col_name, col_info in table_info['columns'].items():
        col_def = f"  {col_name} {col_info['type']}"
        if not col_info.get('nullable', True):
            col_def += " NOT NULL"
        if col_info.get('description'):
            col_def += f" -- {col_info['description']}"
        columns.append(col_def)
    
    ddl = f"CREATE TABLE {table_name} (\n"
    ddl += ",\n".join(columns)
    ddl += "\n);"
    
    if table_info.get('description'):
        ddl += f"\n-- {table_info['description']}"
    
    return ddl
