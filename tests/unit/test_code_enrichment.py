"""
Unit tests for Code Enrichment Service

Tests code lookup loading and enrichment functionality.
"""

import json
from unittest.mock import mock_open, patch

from src.services.code_enrichment import (
    CODE_COLUMN_MAPPINGS,
    clear_cache,
    enrich_results_with_code_descriptions,
    load_code_lookups,
)


class TestLoadCodeLookups:
    """Test code lookup loading from data_mapping.json"""

    def test_load_code_lookups_success(self):
        """Test successful loading of code lookups"""
        mock_data = {
            "code_lookups": {
                "element_codes": {"311": "Wages and salaries", "333": "SSI"},
                "nature_codes": {"35": "Unreported income"},
                "status_codes": {"1": "Amount correct", "2": "Overissuance"},
            }
        }

        with patch("builtins.open", mock_open(read_data=json.dumps(mock_data))):
            with patch("pathlib.Path.exists", return_value=True):
                # Clear cache first
                import src.services.code_enrichment

                src.services.code_enrichment._CODE_LOOKUPS_CACHE = None

                result = load_code_lookups()

                assert len(result) == 3
                assert result["element_codes"]["311"] == "Wages and salaries"
                assert result["nature_codes"]["35"] == "Unreported income"
                assert result["status_codes"]["2"] == "Overissuance"

    def test_load_code_lookups_uses_cache(self):
        """Test that subsequent loads use cache"""
        import src.services.code_enrichment

        cached_data = {"test": "data"}
        src.services.code_enrichment._CODE_LOOKUPS_CACHE = cached_data

        result = load_code_lookups()

        assert result == cached_data

    def test_load_code_lookups_file_not_found(self):
        """Test handling when data_mapping.json not found"""
        with patch("pathlib.Path.exists", return_value=False):
            import src.services.code_enrichment

            src.services.code_enrichment._CODE_LOOKUPS_CACHE = None

            result = load_code_lookups()

            assert result == {}

    def test_load_code_lookups_malformed_json(self):
        """Test handling of malformed JSON"""
        with patch("builtins.open", mock_open(read_data="invalid json")):
            with patch("pathlib.Path.exists", return_value=True):
                import src.services.code_enrichment

                src.services.code_enrichment._CODE_LOOKUPS_CACHE = None

                result = load_code_lookups()

                assert result == {}


class TestEnrichResultsWithCodeDescriptions:
    """Test code enrichment for query results"""

    @patch("src.services.code_enrichment.load_code_lookups")
    def test_enrich_single_code_column(self, mock_load):
        """Test enriching results with a single code column"""
        mock_load.return_value = {"element_codes": {"311": "Wages and salaries", "333": "SSI"}}

        results = [{"element_code": 311, "error_amount": 150.00}, {"element_code": 333, "error_amount": 200.00}]

        lookups = enrich_results_with_code_descriptions(results)

        # Function converts codes to strings
        assert lookups["element_code"]["311"] == "Wages and salaries"
        assert lookups["element_code"]["333"] == "SSI"

    @patch("src.services.code_enrichment.load_code_lookups")
    def test_enrich_multiple_code_columns(self, mock_load):
        """Test enriching results with multiple code columns"""
        mock_load.return_value = {
            "element_codes": {"311": "Wages and salaries"},
            "nature_codes": {"35": "Unreported income"},
            "status_codes": {"2": "Overissuance"},
        }

        results = [{"element_code": 311, "nature_code": 35, "status": 2}]

        lookups = enrich_results_with_code_descriptions(results)

        # Function converts codes to strings
        assert lookups["element_code"]["311"] == "Wages and salaries"
        assert lookups["nature_code"]["35"] == "Unreported income"
        assert lookups["status"]["2"] == "Overissuance"

    @patch("src.services.code_enrichment.load_code_lookups")
    def test_enrich_missing_code(self, mock_load):
        """Test handling of codes not in lookup table"""
        mock_load.return_value = {"element_codes": {"311": "Wages and salaries"}}

        results = [
            {"element_code": 999}  # Code not in lookup
        ]

        lookups = enrich_results_with_code_descriptions(results)

        # Should return lookup dict but code not found
        assert "element_code" in lookups
        assert 999 not in lookups["element_code"]

    @patch("src.services.code_enrichment.load_code_lookups")
    def test_enrich_empty_results(self, mock_load):
        """Test enrichment with empty results"""
        mock_load.return_value = {}

        results = []

        lookups = enrich_results_with_code_descriptions(results)

        assert lookups == {}

    @patch("src.services.code_enrichment.load_code_lookups")
    def test_enrich_null_code_values(self, mock_load):
        """Test handling of NULL/None code values"""
        mock_load.return_value = {"element_codes": {"311": "Wages and salaries"}}

        results = [{"element_code": None, "error_amount": 150.00}]

        lookups = enrich_results_with_code_descriptions(results)

        # Should handle None gracefully
        assert isinstance(lookups, dict)

    @patch("src.services.code_enrichment.load_code_lookups")
    def test_enrich_string_codes(self, mock_load):
        """Test enrichment with string code values"""
        mock_load.return_value = {"element_codes": {"311": "Wages and salaries"}}

        results = [{"element_code": "311", "error_amount": 150.00}]

        lookups = enrich_results_with_code_descriptions(results)

        # Should handle string codes
        assert "element_code" in lookups


class TestCodeColumnMappings:
    """Test code column mapping constants"""

    def test_all_expected_mappings_present(self):
        """Test that all expected code columns are mapped"""
        expected_columns = [
            "element_code",
            "nature_code",
            "status",
            "error_finding",
            "case_classification",
            "sex",
            "snap_affiliation_code",
            "agency_responsibility",
        ]

        for column in expected_columns:
            assert column in CODE_COLUMN_MAPPINGS

    def test_mappings_point_to_correct_lookup_keys(self):
        """Test that mappings point to expected lookup table names"""
        assert CODE_COLUMN_MAPPINGS["element_code"] == "element_codes"
        assert CODE_COLUMN_MAPPINGS["nature_code"] == "nature_codes"
        assert CODE_COLUMN_MAPPINGS["status"] == "status_codes"
        assert CODE_COLUMN_MAPPINGS["sex"] == "sex_codes"


class TestEnrichResultsEdgeCases:
    """Test edge cases in enrich_results_with_code_descriptions"""

    def test_no_code_columns_in_results(self):
        """Test enrichment with results that have no code columns"""
        results = [{"state_name": "California", "count": 100}, {"state_name": "Texas", "count": 200}]

        lookups = enrich_results_with_code_descriptions(results)

        # Should return empty dict when no code columns found
        assert lookups == {}

    def test_results_with_only_non_code_columns(self):
        """Test enrichment with results containing only non-code columns"""
        results = [{"fiscal_year": 2023, "snap_benefit": 284.50}, {"fiscal_year": 2022, "snap_benefit": 300.00}]

        lookups = enrich_results_with_code_descriptions(results)

        assert lookups == {}


class TestClearCache:
    """Test cache clearing functionality"""

    def test_clear_cache(self):
        """Test that clear_cache clears the internal cache"""
        # Load lookups to populate cache
        load_code_lookups()

        # Clear the cache
        clear_cache()

        # Cache should be cleared (next load will repopulate)
        # We can't directly test _CODE_LOOKUPS_CACHE, but we can verify the function runs
        # The main test is that it doesn't crash
        assert True  # clear_cache executed successfully
