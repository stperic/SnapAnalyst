# Dataset Template

This is a template for creating new datasets in the SnapAnalyst multi-dataset architecture.

## Quick Start

1. **Copy this template:**
   ```bash
   cp -r datasets/_template datasets/your_dataset_name
   ```

2. **Edit the configuration:**
   - `config.yaml` - Dataset metadata and table structure
   - `__init__.py` - Python configuration class
   - `data_mapping.json` - Code lookups for Vanna training
   - `training/query_examples.json` - Example queries for Vanna training

3. **Create your models:**
   - `models.py` - SQLAlchemy models for your tables
   - `reference_models.py` - Lookup/reference table models (optional)

4. **Create ETL components:**
   - `column_mapping.py` - CSV column to database column mappings
   - `transformer.py` - ETL transformation logic

5. **Add business context:**
   - `prompts.py` - Business terminology and query patterns

6. **Register the dataset:**
   The dataset will be auto-discovered if it has a valid `config.yaml` or `__init__.py`.

## File Structure

```
your_dataset_name/
├── __init__.py           # Dataset configuration class (required)
├── config.yaml           # Dataset metadata (required)
├── data_mapping.json     # Code lookups for Vanna (required)
├── training/
│   └── query_examples.json   # Training examples (recommended)
├── models.py             # SQLAlchemy models (required for new schema)
├── reference_models.py   # Lookup tables (optional)
├── column_mapping.py     # ETL column mappings (required for ETL)
├── transformer.py        # ETL transformer (optional - can reuse base)
└── prompts.py            # Business context (recommended)
```

## Schema Isolation

If you want your dataset in a separate PostgreSQL schema:

1. Set `schema: your_schema_name` in `config.yaml`
2. Enable schema isolation: `dataset_schema_isolation = true` in `.env`
3. Create the schema in PostgreSQL: `CREATE SCHEMA your_schema_name;`

## Sharing Reference Tables

Datasets can share reference tables from the `public` schema by:
1. Not redefining them in your dataset
2. Using FK references to `public.ref_*` tables

## Cross-Dataset Queries

Once registered, Vanna can generate queries that JOIN across datasets:

```sql
SELECT snap.households.state_name, private.cases.case_worker
FROM snap.households
JOIN private.cases ON snap.households.case_id = private.cases.public_ref
```
