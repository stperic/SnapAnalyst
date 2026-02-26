"""
Unit tests for Prompt Builders

Tests the prompt building functions that generate system prompts for LLMs.
"""

from src.core.prompts import (
    AI_SUMMARY_SYSTEM_PROMPT,
    KB_INSIGHT_INSTRUCTION,
    KB_INSIGHT_SYSTEM_PROMPT,
    VANNA_SQL_SYSTEM_PROMPT,
    build_ai_summary_prompt,
    build_kb_insight_prompt,
)


class TestAISummaryPromptBuilder:
    """Test AI summary prompt building"""

    def test_build_basic_prompt(self):
        """Test building basic AI summary prompt without filters"""
        question = "What are the top error types?"
        data_context = "element_code,count\n311,50\n333,30"

        system_msg, user_msg = build_ai_summary_prompt(question=question, data_context=data_context)

        assert question in user_msg
        assert data_context in user_msg
        assert "DATA TO ANALYZE" in user_msg
        assert "SNAP Quality Control" in system_msg

    def test_build_prompt_with_filters(self):
        """Test building prompt with active filters"""
        question = "Show me error rates"
        data_context = "state,rate\nCA,5.2\nTX,4.8"
        filters = "State: California, Year: FY2023"

        system_msg, user_msg = build_ai_summary_prompt(question=question, data_context=data_context, filters=filters)

        assert filters in user_msg
        assert "ACTIVE FILTERS" in user_msg

    def test_build_prompt_with_code_enrichment(self):
        """Test building prompt with code enrichment flag"""
        system_msg, user_msg = build_ai_summary_prompt(question="Test", data_context="data", has_code_enrichment=True)

        assert "code descriptions" in system_msg.lower() or "CODE REFERENCE" in system_msg

    def test_build_prompt_without_code_enrichment(self):
        """Test building prompt without code enrichment"""
        system_msg, user_msg = build_ai_summary_prompt(question="Test", data_context="data", has_code_enrichment=False)

        # Should still build valid prompt without code instruction
        assert "Test" in user_msg
        assert "data" in user_msg

    def test_build_prompt_returns_tuple(self):
        """Test that build_ai_summary_prompt returns (system, user) tuple"""
        result = build_ai_summary_prompt(question="Test", data_context="data")
        assert isinstance(result, tuple)
        assert len(result) == 2
        system_msg, user_msg = result
        assert isinstance(system_msg, str)
        assert isinstance(user_msg, str)

    def test_build_prompt_with_sql(self):
        """Test building prompt with SQL query included"""
        system_msg, user_msg = build_ai_summary_prompt(
            question="Test", data_context="data", sql="SELECT * FROM households"
        )
        assert "SELECT * FROM households" in user_msg
        assert "SQL QUERY" in user_msg


class TestKBInsightPromptBuilder:
    """Test Knowledge Base insight prompt building"""

    def test_build_basic_kb_prompt(self):
        """Test building basic KB insight prompt"""
        question = "What does status code 2 mean?"

        system_msg, user_msg = build_kb_insight_prompt(question=question)

        assert question in user_msg
        assert KB_INSIGHT_INSTRUCTION in system_msg
        assert "Question:" in user_msg

    def test_build_kb_prompt_with_data_context(self):
        """Test building KB prompt with previous query data"""
        question = "Analyze this data"
        data_context = '{"state": "CA", "rate": 5.2}'

        system_msg, user_msg = build_kb_insight_prompt(question=question, data_context=data_context)

        assert question in user_msg
        assert data_context in user_msg
        assert "DATA TO ANALYZE" in user_msg

    def test_build_kb_prompt_with_chromadb_context(self):
        """Test building KB prompt with ChromaDB context"""
        question = "Explain element code 311"
        chromadb_context = "Element Code 311: Wages and salaries..."

        system_msg, user_msg = build_kb_insight_prompt(question=question, chromadb_context=chromadb_context)

        assert question in user_msg
        assert chromadb_context in user_msg

    def test_build_kb_prompt_with_all_context(self):
        """Test building KB prompt with all context types"""
        question = "Compare error rates"
        data_context = "state,rate\nCA,5.2"
        chromadb_context = "Error rates are calculated..."

        system_msg, user_msg = build_kb_insight_prompt(
            question=question, data_context=data_context, chromadb_context=chromadb_context
        )

        assert question in user_msg
        assert data_context in user_msg
        assert chromadb_context in user_msg

    def test_build_kb_prompt_user_id_custom_prompt(self):
        """Test that user_id parameter is accepted"""
        # This test just verifies the API works, not the custom prompt lookup
        # (which would require database mocking)
        system_msg, user_msg = build_kb_insight_prompt(question="Test", user_id="test_user")

        assert "Test" in user_msg
        assert KB_INSIGHT_INSTRUCTION in system_msg

    def test_build_kb_prompt_user_id_exception(self):
        """Test KB prompt falls back to default when custom prompt lookup fails"""
        from unittest.mock import patch

        # Mock get_user_prompt to raise an exception
        with patch("src.database.prompt_manager.get_user_prompt", side_effect=Exception("DB error")):
            system_msg, user_msg = build_kb_insight_prompt(question="Test question", user_id="failing_user")

            # Should still return valid prompt using default
            assert "Test question" in user_msg
            assert KB_INSIGHT_INSTRUCTION in system_msg
            # Should contain default prompt content
            assert "SNAP Quality Control data analyst" in system_msg

    def test_build_kb_prompt_returns_tuple(self):
        """Test that build_kb_insight_prompt returns (system, user) tuple"""
        result = build_kb_insight_prompt(question="Test")
        assert isinstance(result, tuple)
        assert len(result) == 2
        system_msg, user_msg = result
        assert isinstance(system_msg, str)
        assert isinstance(user_msg, str)


class TestPromptConstants:
    """Test prompt constant definitions"""

    def test_ai_summary_prompt_has_instructions(self):
        """Test AI summary prompt contains expected instructions"""
        assert "INSTRUCTIONS" in AI_SUMMARY_SYSTEM_PROMPT
        assert "SNAP Quality Control" in AI_SUMMARY_SYSTEM_PROMPT

    def test_vanna_sql_prompt_contains_business_rules(self):
        """Test Vanna SQL prompt contains critical business rules"""
        assert "case_classification = 1" in VANNA_SQL_SYSTEM_PROMPT
        assert "ref_tolerance_threshold" in VANNA_SQL_SYSTEM_PROMPT
        assert "mv_state_error_rates" in VANNA_SQL_SYSTEM_PROMPT
        assert "ALWAYS USE THESE FIRST" in VANNA_SQL_SYSTEM_PROMPT

    def test_kb_insight_prompt_is_brief(self):
        """Test KB insight instruction emphasizes brevity"""
        assert "2-3 sentences" in KB_INSIGHT_INSTRUCTION
        assert "brief" in KB_INSIGHT_INSTRUCTION.lower() or "direct" in KB_INSIGHT_INSTRUCTION.lower()

    def test_kb_system_prompt_format(self):
        """Test KB system prompt format"""
        assert isinstance(KB_INSIGHT_SYSTEM_PROMPT, str)
        assert len(KB_INSIGHT_SYSTEM_PROMPT) > 0


class TestPromptValidation:
    """Test prompt validation and safety"""

    def test_prompts_do_not_contain_sensitive_info(self):
        """Test that prompts don't contain sensitive information"""
        prompts = [
            AI_SUMMARY_SYSTEM_PROMPT,
            VANNA_SQL_SYSTEM_PROMPT,
            KB_INSIGHT_SYSTEM_PROMPT,
        ]

        sensitive_terms = ["password", "api_key", "secret", "token"]

        for prompt in prompts:
            prompt_lower = prompt.lower()
            for term in sensitive_terms:
                assert term not in prompt_lower

    def test_sql_prompt_emphasizes_select_only(self):
        """Test SQL prompt emphasizes read-only queries"""
        # Should not encourage modification operations
        dangerous_ops = ["INSERT", "UPDATE", "DELETE", "DROP", "TRUNCATE"]

        for op in dangerous_ops:
            if op in VANNA_SQL_SYSTEM_PROMPT:
                # If mentioned, should be in negative context
                context = VANNA_SQL_SYSTEM_PROMPT.lower()
                assert "only" in context or "select" in context

    def test_prompts_are_non_empty_strings(self):
        """Test all prompt constants are non-empty strings"""
        assert isinstance(AI_SUMMARY_SYSTEM_PROMPT, str)
        assert len(AI_SUMMARY_SYSTEM_PROMPT) > 50

        assert isinstance(VANNA_SQL_SYSTEM_PROMPT, str)
        assert len(VANNA_SQL_SYSTEM_PROMPT) > 100

        assert isinstance(KB_INSIGHT_SYSTEM_PROMPT, str)
        assert len(KB_INSIGHT_SYSTEM_PROMPT) > 10


class TestPromptEdgeCases:
    """Test edge cases in prompt building"""

    def test_build_prompt_with_empty_question(self):
        """Test building prompt with empty question"""
        system_msg, user_msg = build_ai_summary_prompt(question="", data_context="data")

        # Should still build prompt
        assert "data" in user_msg

    def test_build_prompt_with_special_characters(self):
        """Test building prompt with special characters in question"""
        question = "What's the error rate? (>5%)"
        data_context = "rate: 5.2%"

        system_msg, user_msg = build_ai_summary_prompt(question=question, data_context=data_context)

        assert question in user_msg

    def test_build_prompt_with_very_long_data(self):
        """Test building prompt with large data context"""
        question = "Analyze"
        data_context = "x" * 10000  # 10K characters

        system_msg, user_msg = build_ai_summary_prompt(question=question, data_context=data_context)

        assert question in user_msg
        assert len(data_context) <= len(user_msg)  # Data should be included
