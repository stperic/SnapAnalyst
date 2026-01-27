"""
Unit tests for AI Summary Service

Tests AI-powered summary generation with dynamic prompt sizing.
"""

from unittest.mock import patch

import pytest

from src.services.ai_summary import (
    _build_code_reference,
    _format_results_for_llm,
    generate_ai_summary,
    generate_simple_summary,
)


class TestGenerateAISummary:
    """Test main AI summary generation function"""

    @pytest.mark.asyncio
    async def test_empty_results(self):
        """Test handling of empty results"""
        summary = await generate_ai_summary(
            question="Test question",
            sql="SELECT * FROM test",
            results=[],
            row_count=0,
            filters=""
        )

        assert "no results" in summary.lower() or "0 rows" in summary.lower()

    @pytest.mark.asyncio
    async def test_single_value_result(self):
        """Test special handling for single-row single-column results"""
        results = [{"count": 1234}]

        summary = await generate_ai_summary(
            question="How many households?",
            sql="SELECT COUNT(*) as count FROM households",
            results=results,
            row_count=1,
            filters=""
        )

        assert "1,234" in summary  # Should format with commas
        assert "count" in summary

    @pytest.mark.asyncio
    async def test_single_value_with_filters(self):
        """Test single-value result includes filter information"""
        results = [{"total": 5000}]

        summary = await generate_ai_summary(
            question="What is the total?",
            sql="SELECT SUM(amount) as total FROM data",
            results=results,
            row_count=1,
            filters="State: California, Year: FY2023"
        )

        assert "5,000" in summary
        assert "California" in summary or "filtered" in summary.lower()

    @pytest.mark.asyncio
    @patch('src.services.ai_summary.enrich_results_with_code_descriptions')
    @patch('src.services.ai_summary.call_api')
    async def test_ai_summary_success(self, mock_call_api, mock_enrich):
        """Test successful AI summary generation"""
        mock_enrich.return_value = {}
        mock_call_api.return_value = {"text": "AI generated summary here"}

        results = [
            {"state": "California", "count": 100},
            {"state": "Texas", "count": 90}
        ]

        summary = await generate_ai_summary(
            question="Top states by count",
            sql="SELECT state, COUNT(*) as count FROM data GROUP BY state",
            results=results,
            row_count=2,
            filters=""
        )

        assert summary == "AI generated summary here"
        mock_call_api.assert_called_once()

    @pytest.mark.asyncio
    @patch('src.services.ai_summary.enrich_results_with_code_descriptions')
    @patch('src.services.ai_summary.call_api')
    @patch('src.core.config.settings')
    async def test_prompt_too_large_fallback(self, mock_settings, mock_call_api, mock_enrich):
        """Test fallback to simple summary when prompt too large"""
        mock_enrich.return_value = {}
        mock_settings.llm_kb_max_prompt_size = 100  # Very small limit

        # Create large result set
        results = [{"col1": i, "col2": f"value_{i}"} for i in range(1000)]

        summary = await generate_ai_summary(
            question="Show me data",
            sql="SELECT * FROM large_table",
            results=results,
            row_count=1000,
            filters=""
        )

        # Should use simple summary, not call API
        mock_call_api.assert_not_called()
        assert "1,000" in summary or "1000" in summary

    @pytest.mark.asyncio
    @patch('src.services.ai_summary.enrich_results_with_code_descriptions')
    @patch('src.services.ai_summary.call_api')
    async def test_api_call_failure(self, mock_call_api, mock_enrich):
        """Test fallback when API call fails"""
        mock_enrich.return_value = {}
        mock_call_api.side_effect = Exception("API Error")

        results = [{"state": "California", "count": 100}]

        summary = await generate_ai_summary(
            question="Show states",
            sql="SELECT * FROM states",
            results=results,
            row_count=1,
            filters=""
        )

        # Should fall back to simple summary
        assert isinstance(summary, str)
        assert len(summary) > 0

    @pytest.mark.asyncio
    @patch('src.services.ai_summary.enrich_results_with_code_descriptions')
    @patch('src.services.ai_summary.call_api')
    async def test_api_returns_empty_response(self, mock_call_api, mock_enrich):
        """Test handling when API returns empty response"""
        mock_enrich.return_value = {}
        mock_call_api.return_value = {}  # No "text" field

        results = [{"count": 50}]

        summary = await generate_ai_summary(
            question="Count",
            sql="SELECT COUNT(*)",
            results=results,
            row_count=1,
            filters=""
        )

        # Should fall back to simple summary
        assert isinstance(summary, str)
        assert "50" in summary

    @pytest.mark.asyncio
    @patch('src.services.ai_summary.enrich_results_with_code_descriptions')
    @patch('src.services.ai_summary.call_api')
    async def test_with_code_enrichment(self, mock_call_api, mock_enrich):
        """Test summary generation with code enrichment"""
        mock_enrich.return_value = {
            "element_code": {"311": "Wages and salaries", "333": "SSI"}
        }
        mock_call_api.return_value = {"text": "Summary with codes"}

        results = [
            {"element_code": 311, "count": 50},
            {"element_code": 333, "count": 30}
        ]

        summary = await generate_ai_summary(
            question="Error types",
            sql="SELECT element_code, COUNT(*) FROM errors",
            results=results,
            row_count=2,
            filters=""
        )

        assert summary == "Summary with codes"
        # Verify call_api was called with prompt containing code reference
        call_args = mock_call_api.call_args
        prompt = call_args[1]["data"]["prompt"]
        assert "311" in prompt
        assert "Wages and salaries" in prompt

    @pytest.mark.asyncio
    @patch('src.services.ai_summary.enrich_results_with_code_descriptions')
    @patch('src.services.ai_summary.call_api')
    @patch('src.core.config.settings')
    async def test_max_tokens_for_small_results(self, mock_settings, mock_call_api, mock_enrich):
        """Test that small result sets use smaller max_tokens"""
        mock_enrich.return_value = {}
        mock_call_api.return_value = {"text": "Short summary"}
        mock_settings.llm_kb_max_prompt_size = 100000
        mock_settings.llm_kb_max_tokens = 300

        # Use 5 rows with multiple columns to avoid single-value early return
        results = [
            {"state": "CA", "count": 10},
            {"state": "TX", "count": 20},
            {"state": "NY", "count": 30},
            {"state": "FL", "count": 40},
            {"state": "IL", "count": 50}
        ]

        await generate_ai_summary(
            question="Show states",
            sql="SELECT state, count FROM data",
            results=results,
            row_count=5,
            filters=""
        )

        # Should use min(150, base_max_tokens) for small results (row_count <= 20)
        call_args = mock_call_api.call_args
        max_tokens = call_args[1]["data"]["max_tokens"]
        assert max_tokens == 150


class TestGenerateSimpleSummary:
    """Test simple fallback summary generation"""

    def test_single_row_single_value(self):
        """Test simple summary for single row with single value"""
        results = [{"total": 12345}]

        summary = generate_simple_summary(
            question="What is total?",
            row_count=1,
            results=results,
            filters=""
        )

        assert isinstance(summary, str)
        assert len(summary) > 0

    def test_single_row_multiple_columns(self):
        """Test simple summary for single row with multiple columns"""
        results = [{"state": "California", "count": 100}]

        summary = generate_simple_summary(
            question="Show data",
            row_count=1,
            results=results,
            filters=""
        )

        assert "1" in summary
        assert isinstance(summary, str)

    def test_few_results(self):
        """Test simple summary for few results (2-10)"""
        summary = generate_simple_summary(
            question="Show data",
            row_count=5,
            results=[],
            filters=""
        )

        assert "5" in summary

    def test_medium_results(self):
        """Test simple summary for medium results (11-100)"""
        summary = generate_simple_summary(
            question="Show data",
            row_count=50,
            results=[],
            filters=""
        )

        assert "50" in summary

    def test_large_results(self):
        """Test simple summary for large results (>100)"""
        summary = generate_simple_summary(
            question="Show data",
            row_count=500,
            results=[],
            filters=""
        )

        assert "500" in summary

    def test_with_filters(self):
        """Test simple summary includes filter information"""
        summary = generate_simple_summary(
            question="Show data",
            row_count=10,
            results=[],
            filters="State: California, Year: FY2023"
        )

        assert "California" in summary or "filtered" in summary.lower()

    def test_without_filters(self):
        """Test simple summary without filters"""
        summary = generate_simple_summary(
            question="Show data",
            row_count=10,
            results=[],
            filters=""
        )

        assert isinstance(summary, str)
        assert len(summary) > 0


class TestFormatResultsForLLM:
    """Test result formatting for LLM"""

    def test_format_float_values(self):
        """Test rounding of float values to 2 decimals"""
        data = [
            {"rate": 5.123456, "amount": 100.999}
        ]

        formatted = _format_results_for_llm(data)

        assert formatted[0]["rate"] == 5.12
        assert formatted[0]["amount"] == 101.0

    def test_format_string_numeric_values(self):
        """Test conversion and rounding of string numeric values"""
        data = [
            {"rate": "5.678", "count": "10.999"}
        ]

        formatted = _format_results_for_llm(data)

        assert formatted[0]["rate"] == 5.68
        assert formatted[0]["count"] == 11.0

    def test_preserve_non_numeric_strings(self):
        """Test that non-numeric strings are preserved"""
        data = [
            {"state": "California", "status": "Active"}
        ]

        formatted = _format_results_for_llm(data)

        assert formatted[0]["state"] == "California"
        assert formatted[0]["status"] == "Active"

    def test_preserve_integer_values(self):
        """Test that integer values are preserved"""
        data = [
            {"count": 100, "year": 2023}
        ]

        formatted = _format_results_for_llm(data)

        assert formatted[0]["count"] == 100
        assert formatted[0]["year"] == 2023

    def test_handle_none_values(self):
        """Test handling of None values"""
        data = [
            {"state": "California", "amount": None}
        ]

        formatted = _format_results_for_llm(data)

        assert formatted[0]["state"] == "California"
        assert formatted[0]["amount"] is None

    def test_empty_data(self):
        """Test formatting of empty data"""
        data = []

        formatted = _format_results_for_llm(data)

        assert formatted == []

    def test_multiple_rows(self):
        """Test formatting multiple rows"""
        data = [
            {"rate": 5.123, "count": 100},
            {"rate": 6.789, "count": 200},
            {"rate": 7.456, "count": 300}
        ]

        formatted = _format_results_for_llm(data)

        assert len(formatted) == 3
        assert formatted[0]["rate"] == 5.12
        assert formatted[1]["rate"] == 6.79
        assert formatted[2]["rate"] == 7.46


class TestBuildCodeReference:
    """Test code reference section building"""

    def test_empty_enrichment(self):
        """Test that empty enrichment returns empty string"""
        result = _build_code_reference({})

        assert result == ""

    def test_single_code_column(self):
        """Test building reference for single code column"""
        enrichment = {
            "element_code": {
                "311": "Wages and salaries",
                "333": "SSI"
            }
        }

        result = _build_code_reference(enrichment)

        assert "Element Code:" in result
        assert "311" in result
        assert "Wages and salaries" in result
        assert "333" in result
        assert "SSI" in result

    def test_multiple_code_columns(self):
        """Test building reference for multiple code columns"""
        enrichment = {
            "element_code": {"311": "Wages and salaries"},
            "status": {"2": "Overissuance"}
        }

        result = _build_code_reference(enrichment)

        assert "Element Code:" in result
        assert "Status:" in result
        assert "311" in result
        assert "Wages and salaries" in result
        assert "2" in result
        assert "Overissuance" in result

    def test_numeric_sorting(self):
        """Test that codes are sorted numerically"""
        enrichment = {
            "element_code": {
                "333": "SSI",
                "50": "Other",
                "311": "Wages"
            }
        }

        result = _build_code_reference(enrichment)

        # Find positions of codes in result
        pos_50 = result.find("Code 50")
        pos_311 = result.find("Code 311")
        pos_333 = result.find("Code 333")

        # Should be in numeric order
        assert pos_50 < pos_311 < pos_333

    def test_mixed_numeric_and_non_numeric_codes(self):
        """Test sorting with mix of numeric and non-numeric codes"""
        enrichment = {
            "status": {
                "2": "Overissuance",
                "A": "Approved",
                "1": "Correct"
            }
        }

        result = _build_code_reference(enrichment)

        # Numeric codes should come first
        assert "Code 1" in result
        assert "Code 2" in result
        assert "Code A" in result

    def test_code_reference_structure(self):
        """Test that code reference has proper header and footer"""
        enrichment = {
            "element_code": {"311": "Wages"}
        }

        result = _build_code_reference(enrichment)

        # Should have some structure (header/footer defined in prompts.py)
        assert len(result) > 20  # More than just the code
        assert "311" in result


class TestAISummaryEdgeCases:
    """Test edge cases in AI summary generation"""

    @pytest.mark.asyncio
    async def test_malformed_results(self):
        """Test handling of malformed results"""
        results = [None, {"broken": "data"}, {}]

        # Should not crash
        summary = await generate_ai_summary(
            question="Test",
            sql="SELECT *",
            results=results,
            row_count=3,
            filters=""
        )

        assert isinstance(summary, str)

    @pytest.mark.asyncio
    @patch('src.services.ai_summary.enrich_results_with_code_descriptions')
    async def test_enrichment_raises_exception(self, mock_enrich):
        """Test handling when code enrichment raises exception"""
        mock_enrich.side_effect = Exception("Enrichment failed")

        results = [{"count": 100}]

        # Should fall back to simple summary
        summary = await generate_ai_summary(
            question="Test",
            sql="SELECT COUNT(*)",
            results=results,
            row_count=1,
            filters=""
        )

        assert isinstance(summary, str)
        assert "100" in summary

    def test_format_with_very_large_numbers(self):
        """Test formatting with very large float numbers"""
        data = [{"amount": 123456789.123456}]

        formatted = _format_results_for_llm(data)

        assert formatted[0]["amount"] == 123456789.12

    def test_format_with_negative_numbers(self):
        """Test formatting with negative numbers"""
        data = [{"amount": -123.456}]

        formatted = _format_results_for_llm(data)

        assert formatted[0]["amount"] == -123.46

    @pytest.mark.asyncio
    @patch('src.clients.api_client.call_api')
    @patch('src.services.ai_summary.enrich_results_with_code_descriptions')
    async def test_api_response_missing_text_key(self, mock_enrich, mock_call_api):
        """Test fallback when API response doesn't have 'text' key"""
        mock_enrich.return_value = ([], {})
        # API returns response but without "text" key
        mock_call_api.return_value = {"status": "success"}  # Missing "text" key

        results = [{"count": 5}]

        summary = await generate_ai_summary(
            question="Test",
            sql="SELECT COUNT(*)",
            results=results,
            row_count=1,
            filters=""
        )

        # Should fall back to simple summary
        assert isinstance(summary, str)
        assert "5" in summary
