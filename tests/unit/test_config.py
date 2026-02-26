"""
Unit tests for Configuration Management

Tests settings properties and model selection logic.
"""

from unittest.mock import patch

from src.core.config import Settings, get_settings


class TestSettingsProperties:
    """Test Settings property methods"""

    def test_is_development(self):
        """Test is_development property"""
        with patch.dict(
            "os.environ",
            {"ENVIRONMENT": "development", "DATABASE_URL": "postgresql://localhost/test", "SECRET_KEY": "test-key"},
        ):
            settings = Settings()
            assert settings.is_development is True

    def test_is_production(self):
        """Test is_production property"""
        with patch.dict(
            "os.environ",
            {"ENVIRONMENT": "production", "DATABASE_URL": "postgresql://localhost/test", "SECRET_KEY": "test-key"},
        ):
            settings = Settings()
            assert settings.is_production is True

    def test_is_not_production_in_dev(self):
        """Test is_production returns False in development"""
        with patch.dict(
            "os.environ",
            {"ENVIRONMENT": "development", "DATABASE_URL": "postgresql://localhost/test", "SECRET_KEY": "test-key"},
        ):
            settings = Settings()
            assert settings.is_production is False


class TestSQLModel:
    """Test sql_model property"""

    def test_sql_model_openai_default(self):
        """Test SQL model default for OpenAI"""
        with patch.dict(
            "os.environ",
            {
                "LLM_PROVIDER": "openai",
                "DATABASE_URL": "postgresql://localhost/test",
                "SECRET_KEY": "test-key",
                "LLM_SQL_MODEL": "",
            },
            clear=False,
        ):
            settings = Settings()
            assert settings.sql_model == "gpt-4.1"

    def test_sql_model_anthropic_default(self):
        """Test SQL model default for Anthropic"""
        with patch.dict(
            "os.environ",
            {
                "LLM_PROVIDER": "anthropic",
                "DATABASE_URL": "postgresql://localhost/test",
                "SECRET_KEY": "test-key",
                "LLM_SQL_MODEL": "",
            },
            clear=False,
        ):
            settings = Settings()
            assert settings.sql_model == "claude-sonnet-4-20250514"

    def test_sql_model_ollama_default(self):
        """Test SQL model default for Ollama"""
        with patch.dict(
            "os.environ",
            {
                "LLM_PROVIDER": "ollama",
                "DATABASE_URL": "postgresql://localhost/test",
                "SECRET_KEY": "test-key",
                "LLM_SQL_MODEL": "",
            },
            clear=False,
        ):
            settings = Settings()
            assert settings.sql_model == "llama3.1:8b"

    def test_sql_model_azure_openai_default(self):
        """Test SQL model default for Azure OpenAI"""
        with patch.dict(
            "os.environ",
            {
                "LLM_PROVIDER": "azure_openai",
                "DATABASE_URL": "postgresql://localhost/test",
                "SECRET_KEY": "test-key",
                "LLM_SQL_MODEL": "",
            },
            clear=False,
        ):
            settings = Settings()
            assert settings.sql_model == "gpt-4.1"

    def test_sql_model_custom_override(self):
        """Test custom SQL model overrides default"""
        with patch.dict(
            "os.environ",
            {
                "LLM_PROVIDER": "openai",
                "LLM_SQL_MODEL": "gpt-4o",
                "DATABASE_URL": "postgresql://localhost/test",
                "SECRET_KEY": "test-key",
            },
        ):
            settings = Settings()
            assert settings.sql_model == "gpt-4o"


class TestKBModel:
    """Test kb_model property"""

    def test_kb_model_openai_default(self):
        """Test KB model default for OpenAI"""
        with patch.dict(
            "os.environ",
            {
                "LLM_PROVIDER": "openai",
                "DATABASE_URL": "postgresql://localhost/test",
                "SECRET_KEY": "test-key",
                "LLM_KB_MODEL": "",
                "LLM_SQL_MODEL": "",
            },
            clear=False,
        ):
            settings = Settings()
            assert settings.kb_model == "gpt-4.1-mini"

    def test_kb_model_anthropic_default(self):
        """Test KB model default for Anthropic"""
        with patch.dict(
            "os.environ",
            {
                "LLM_PROVIDER": "anthropic",
                "DATABASE_URL": "postgresql://localhost/test",
                "SECRET_KEY": "test-key",
                "LLM_KB_MODEL": "",
                "LLM_SQL_MODEL": "",
            },
            clear=False,
        ):
            settings = Settings()
            assert settings.kb_model == "claude-haiku-4-5-20251001"

    def test_kb_model_ollama_default(self):
        """Test KB model default for Ollama"""
        with patch.dict(
            "os.environ",
            {
                "LLM_PROVIDER": "ollama",
                "DATABASE_URL": "postgresql://localhost/test",
                "SECRET_KEY": "test-key",
                "LLM_KB_MODEL": "",
                "LLM_SQL_MODEL": "",
            },
            clear=False,
        ):
            settings = Settings()
            assert settings.kb_model == "llama3.1:8b"

    def test_kb_model_custom_override(self):
        """Test custom KB model overrides default"""
        with patch.dict(
            "os.environ",
            {
                "LLM_PROVIDER": "openai",
                "LLM_KB_MODEL": "gpt-4",
                "DATABASE_URL": "postgresql://localhost/test",
                "SECRET_KEY": "test-key",
            },
        ):
            settings = Settings()
            assert settings.kb_model == "gpt-4"


class TestEffectiveSettings:
    """Test effective settings properties"""

    def test_effective_sql_max_tokens_default(self):
        """Test effective SQL max tokens uses default"""
        with patch.dict("os.environ", {"DATABASE_URL": "postgresql://localhost/test", "SECRET_KEY": "test-key"}):
            settings = Settings()
            assert settings.effective_sql_max_tokens == settings.llm_max_tokens

    def test_effective_sql_max_tokens_custom(self):
        """Test effective SQL max tokens uses custom value"""
        with patch.dict(
            "os.environ",
            {"LLM_SQL_MAX_TOKENS": "4000", "DATABASE_URL": "postgresql://localhost/test", "SECRET_KEY": "test-key"},
        ):
            settings = Settings()
            assert settings.effective_sql_max_tokens == 4000

    def test_effective_sql_temperature_default(self):
        """Test effective SQL temperature uses default"""
        with patch.dict("os.environ", {"DATABASE_URL": "postgresql://localhost/test", "SECRET_KEY": "test-key"}):
            settings = Settings()
            assert settings.effective_sql_temperature == settings.llm_temperature

    def test_effective_sql_temperature_custom(self):
        """Test effective SQL temperature uses custom value"""
        with patch.dict(
            "os.environ",
            {"LLM_SQL_TEMPERATURE": "0.5", "DATABASE_URL": "postgresql://localhost/test", "SECRET_KEY": "test-key"},
        ):
            settings = Settings()
            assert settings.effective_sql_temperature == 0.5

    def test_effective_kb_temperature_default(self):
        """Test effective KB temperature uses default"""
        with patch.dict("os.environ", {"DATABASE_URL": "postgresql://localhost/test", "SECRET_KEY": "test-key"}):
            settings = Settings()
            assert settings.effective_kb_temperature == settings.llm_temperature

    def test_effective_kb_temperature_custom(self):
        """Test effective KB temperature uses custom value"""
        with patch.dict(
            "os.environ",
            {"LLM_KB_TEMPERATURE": "0.7", "DATABASE_URL": "postgresql://localhost/test", "SECRET_KEY": "test-key"},
        ):
            settings = Settings()
            assert settings.effective_kb_temperature == 0.7


class TestGetSettings:
    """Test get_settings caching"""

    def test_get_settings_returns_instance(self):
        """Test get_settings returns Settings instance"""
        settings = get_settings()
        assert isinstance(settings, Settings)

    def test_get_settings_is_cached(self):
        """Test get_settings returns same instance"""
        settings1 = get_settings()
        settings2 = get_settings()

        # Should return same cached instance
        assert settings1 is settings2
