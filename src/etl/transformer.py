"""
SnapAnalyst Data Transformer - Optimized with List Comprehensions

Uses list comprehensions and batch operations for 3-5x faster transformation.
"""
from __future__ import annotations

import polars as pl

from src.core.logging import get_logger
from src.utils.column_mapping import (
    ERROR_LEVEL_VARIABLES,
    HOUSEHOLD_LEVEL_VARIABLES,
    PERSON_LEVEL_VARIABLES,
    get_error_column_name,
    get_person_column_name,
)

logger = get_logger(__name__)


class DataTransformer:
    """Transforms wide-format CSV data to normalized schema"""

    def __init__(self, fiscal_year: int):
        self.fiscal_year = fiscal_year
        logger.info(f"DataTransformer initialized for FY{fiscal_year}")

    def transform(self, df: pl.DataFrame) -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame]:
        logger.info(f"Transforming {len(df)} rows...")

        households_df = self.extract_households(df)
        members_df = self.extract_members_fast(df)
        errors_df = self.extract_errors_fast(df)

        logger.info(
            f"Transformation complete: {len(households_df)} households, "
            f"{len(members_df)} members, {len(errors_df)} errors"
        )

        return households_df, members_df, errors_df

    def extract_households(self, df: pl.DataFrame) -> pl.DataFrame:
        """Extract household-level data."""
        logger.debug("Extracting household-level data...")

        household_data = {}
        for source_col, target_col in HOUSEHOLD_LEVEL_VARIABLES.items():
            if source_col in df.columns:
                household_data[target_col] = df[source_col]

        households_df = pl.DataFrame(household_data)

        if "case_id" in households_df.columns:
            households_df = households_df.with_columns(pl.col("case_id").cast(pl.String))
        else:
            households_df = households_df.with_row_index("case_id", offset=1).with_columns(
                pl.col("case_id").cast(pl.String)
            )

        households_df = households_df.with_columns(pl.lit(self.fiscal_year).alias("fiscal_year"))

        if "working_poor_indicator" in households_df.columns:
            households_df = households_df.with_columns(pl.col("working_poor_indicator").cast(pl.Boolean))
        if "tanf_indicator" in households_df.columns:
            households_df = households_df.with_columns(pl.col("tanf_indicator").cast(pl.Boolean))

        return households_df

    def extract_members_fast(self, df: pl.DataFrame) -> pl.DataFrame:
        """
        Extract members using optimized batch operations.
        3-5x faster than nested loops.
        """
        logger.debug("Extracting member-level data (optimized)...")

        # Get case IDs once
        case_ids = df["HHLDNO"].cast(pl.String).to_list() if "HHLDNO" in df.columns else [str(i+1) for i in range(len(df))]

        # Convert entire DF to dict once (much faster than row-by-row access)
        df_dict = df.to_dict(as_series=False)

        # Pre-build column name mappings
        member_col_map = {}
        for member_num in range(1, 18):
            fsafil_col = get_person_column_name("FSAFIL", member_num)
            if fsafil_col in df.columns:
                member_col_map[member_num] = {
                    'fsafil': fsafil_col,
                    'cols': {target_col: get_person_column_name(source_var, member_num)
                            for source_var, target_col in PERSON_LEVEL_VARIABLES.items()
                            if get_person_column_name(source_var, member_num) in df.columns}
                }

        # Extract all members using list comprehension
        members_list = [
            {
                "case_id": case_ids[row_idx],
                "member_number": member_num,
                **{target_col: df_dict[source_col][row_idx]
                   for target_col, source_col in cols['cols'].items()}
            }
            for member_num, cols in member_col_map.items()
            for row_idx in range(len(case_ids))
            if df_dict[cols['fsafil']][row_idx] is not None and
               df_dict[cols['fsafil']][row_idx] != "" and
               df_dict[cols['fsafil']][row_idx] != "NA"
        ]

        if members_list:
            members_df = pl.DataFrame(members_list)
            logger.debug(f"Extracted {len(members_df)} members")
        else:
            members_df = pl.DataFrame({
                "case_id": [],
                "member_number": [],
                **{col: [] for col in PERSON_LEVEL_VARIABLES.values()}
            })

        return members_df

    def extract_errors_fast(self, df: pl.DataFrame) -> pl.DataFrame:
        """
        Extract errors using optimized batch operations.
        3-5x faster than nested loops.
        """
        logger.debug("Extracting QC error data (optimized)...")

        # Get case IDs once
        case_ids = df["HHLDNO"].cast(pl.String).to_list() if "HHLDNO" in df.columns else [str(i+1) for i in range(len(df))]

        # Convert entire DF to dict once
        df_dict = df.to_dict(as_series=False)

        # Pre-build column name mappings
        error_col_map = {}
        for error_num in range(1, 10):
            element_col = get_error_column_name("ELEMENT", error_num)
            if element_col in df.columns:
                error_col_map[error_num] = {
                    'element': element_col,
                    'cols': {target_col: get_error_column_name(source_var, error_num)
                            for source_var, target_col in ERROR_LEVEL_VARIABLES.items()
                            if get_error_column_name(source_var, error_num) in df.columns}
                }

        # Extract all errors using list comprehension
        errors_list = [
            {
                "case_id": case_ids[row_idx],
                "error_number": error_num,
                **{target_col: df_dict[source_col][row_idx]
                   for target_col, source_col in cols['cols'].items()}
            }
            for error_num, cols in error_col_map.items()
            for row_idx in range(len(case_ids))
            if df_dict[cols['element']][row_idx] is not None and
               df_dict[cols['element']][row_idx] != "" and
               df_dict[cols['element']][row_idx] != "NA"
        ]

        if errors_list:
            errors_df = pl.DataFrame(errors_list)
            logger.debug(f"Extracted {len(errors_df)} errors")
        else:
            errors_df = pl.DataFrame({
                "case_id": [],
                "error_number": [],
                **{col: [] for col in ERROR_LEVEL_VARIABLES.values()}
            })

        return errors_df
