"""
SnapAnalyst Data Transformer

Transforms wide-format SNAP QC data to normalized long format.
"""
from decimal import Decimal
from typing import Any, Dict, List, Optional

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
        """
        Initialize transformer.
        
        Args:
            fiscal_year: Fiscal year of the data
        """
        self.fiscal_year = fiscal_year
        logger.info(f"DataTransformer initialized for FY{fiscal_year}")
    
    def transform(self, df: pl.DataFrame) -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame]:
        """
        Transform wide-format DataFrame to 3 normalized DataFrames.
        
        Args:
            df: Wide-format input DataFrame
            
        Returns:
            Tuple of (households_df, members_df, errors_df)
        """
        logger.info(f"Transforming {len(df)} rows...")
        
        households_df = self.extract_households(df)
        members_df = self.extract_members(df)
        errors_df = self.extract_errors(df)
        
        logger.info(
            f"Transformation complete: {len(households_df)} households, "
            f"{len(members_df)} members, {len(errors_df)} errors"
        )
        
        return households_df, members_df, errors_df
    
    def extract_households(self, df: pl.DataFrame) -> pl.DataFrame:
        """
        Extract household-level data.
        
        Args:
            df: Wide-format DataFrame
            
        Returns:
            Households DataFrame
        """
        logger.debug("Extracting household-level data...")
        
        # Select and rename columns
        household_data = {}
        
        for source_col, target_col in HOUSEHOLD_LEVEL_VARIABLES.items():
            if source_col in df.columns:
                household_data[target_col] = df[source_col]
            else:
                logger.warning(f"Column {source_col} not found, skipping")
        
        # Add fiscal year
        households_df = pl.DataFrame(household_data)
        
        # case_id is now mapped from HHLDNO (row number / unique unit identifier)
        # case_classification is mapped from CASE (classification code 1-3)
        if "case_id" in households_df.columns:
            # Convert case_id to string for consistency
            households_df = households_df.with_columns(
                pl.col("case_id").cast(pl.String)
            )
            logger.info(f"Using HHLDNO as case_id for {len(households_df)} households")
        else:
            logger.warning("HHLDNO not found in data! Falling back to row numbers.")
            households_df = households_df.with_row_index("case_id", offset=1)
            households_df = households_df.with_columns(
                pl.col("case_id").cast(pl.String)
            )
        
        households_df = households_df.with_columns(
            pl.lit(self.fiscal_year).alias("fiscal_year")
        )
        
        # Convert boolean indicators
        if "working_poor_indicator" in households_df.columns:
            households_df = households_df.with_columns(
                pl.col("working_poor_indicator").cast(pl.Boolean)
            )
        if "tanf_indicator" in households_df.columns:
            households_df = households_df.with_columns(
                pl.col("tanf_indicator").cast(pl.Boolean)
            )
        
        logger.debug(f"Extracted {len(households_df)} households")
        return households_df
    
    def extract_members(self, df: pl.DataFrame) -> pl.DataFrame:
        """
        Extract person-level data by unpivoting members 1-17.
        
        Args:
            df: Wide-format DataFrame
            
        Returns:
            Members DataFrame (long format)
        """
        logger.debug("Extracting member-level data (unpivoting 1-17)...")
        
        members_list = []
        # Use HHLDNO as the unique case ID (row number from source file)
        if "HHLDNO" in df.columns:
            case_ids = [str(val) for val in df["HHLDNO"].to_list()]
            logger.debug(f"Using HHLDNO as case_id for member extraction")
        else:
            # Fallback to row numbers if HHLDNO not available
            case_ids = [str(i+1) for i in range(len(df))]
            logger.warning("HHLDNO not found! Using row numbers as fallback.")
        
        # Iterate through each row (household)
        for row_idx, case_id in enumerate(case_ids):
            row = df[row_idx]
            
            # Extract each member (1-17)
            for member_num in range(1, 18):
                # Check if member exists (FSAFIL must be non-null)
                fsafil_col = get_person_column_name("FSAFIL", member_num)
                if fsafil_col not in df.columns:
                    continue
                
                fsafil_value = row[fsafil_col][0]
                
                # Skip if member doesn't exist
                if fsafil_value is None or (isinstance(fsafil_value, str) and fsafil_value.strip() == ""):
                    continue
                
                # Extract all person-level variables for this member
                member_data = {
                    "case_id": case_id,
                    "member_number": member_num,
                }
                
                for source_var, target_col in PERSON_LEVEL_VARIABLES.items():
                    source_col = get_person_column_name(source_var, member_num)
                    if source_col in df.columns:
                        value = row[source_col][0]
                        # Convert empty strings to None
                        if value == "" or value == "NA":
                            value = None
                        # Convert numeric fields to proper types
                        if target_col in ["wages", "self_employment_income", "social_security", 
                                         "ssi", "tanf", "child_support", "unemployment"]:
                            value = Decimal(str(value)) if value is not None else Decimal("0")
                        member_data[target_col] = value
                
                members_list.append(member_data)
        
        # Convert to DataFrame
        if members_list:
            members_df = pl.DataFrame(members_list)
            logger.debug(f"Extracted {len(members_df)} members from {len(df)} households")
        else:
            # Empty DataFrame with correct schema
            members_df = pl.DataFrame({col: [] for col in PERSON_LEVEL_VARIABLES.values()})
            members_df = members_df.with_columns([
                pl.lit(None).alias("case_id"),
                pl.lit(None).alias("member_number"),
            ])
            logger.warning("No members extracted")
        
        return members_df
    
    def extract_errors(self, df: pl.DataFrame) -> pl.DataFrame:
        """
        Extract QC error data by unpivoting errors 1-9.
        
        Args:
            df: Wide-format DataFrame
            
        Returns:
            Errors DataFrame (long format)
        """
        logger.debug("Extracting QC error data (unpivoting 1-9)...")
        
        errors_list = []
        # Use HHLDNO as the unique case ID (row number from source file)
        if "HHLDNO" in df.columns:
            case_ids = [str(val) for val in df["HHLDNO"].to_list()]
            logger.debug(f"Using HHLDNO as case_id for error extraction")
        else:
            # Fallback to row numbers if HHLDNO not available
            case_ids = [str(i+1) for i in range(len(df))]
            logger.warning("HHLDNO not found! Using row numbers as fallback.")
        
        # Iterate through each row (household)
        for row_idx, case_id in enumerate(case_ids):
            row = df[row_idx]
            
            # Extract each error (1-9)
            for error_num in range(1, 10):
                # Check if error exists (ELEMENT must be non-null)
                element_col = get_error_column_name("ELEMENT", error_num)
                if element_col not in df.columns:
                    continue
                
                element_value = row[element_col][0]
                
                # Skip if error doesn't exist
                if element_value is None or (isinstance(element_value, str) and element_value.strip() == ""):
                    continue
                
                # Extract all error-level variables for this error
                error_data = {
                    "case_id": case_id,
                    "error_number": error_num,
                }
                
                for source_var, target_col in ERROR_LEVEL_VARIABLES.items():
                    source_col = get_error_column_name(source_var, error_num)
                    if source_col in df.columns:
                        value = row[source_col][0]
                        # Convert empty strings to None
                        if value == "" or value == "NA":
                            value = None
                        # Convert amount to Decimal
                        if target_col == "error_amount" and value is not None:
                            value = Decimal(str(value))
                        error_data[target_col] = value
                
                errors_list.append(error_data)
        
        # Convert to DataFrame
        if errors_list:
            errors_df = pl.DataFrame(errors_list)
            logger.debug(f"Extracted {len(errors_df)} errors from {len(df)} households")
        else:
            # Empty DataFrame with correct schema
            errors_df = pl.DataFrame({col: [] for col in ERROR_LEVEL_VARIABLES.values()})
            errors_df = errors_df.with_columns([
                pl.lit(None).alias("case_id"),
                pl.lit(None).alias("error_number"),
            ])
            logger.debug("No errors extracted")
        
        return errors_df
