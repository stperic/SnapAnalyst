"""
LLM Service for Natural Language to SQL Query Generation

Supports multiple LLM providers:
- OpenAI (GPT-4)
- Anthropic (Claude)
- Ollama (Local models)

Uses Vanna.AI with ChromaDB for SQL generation with training data.

Note: Provider classes are in llm_providers.py
      Training logic is in llm_training.py
"""

import time
from typing import Dict, List, Optional, Tuple

from src.core.config import settings
from src.core.logging import get_logger, get_llm_logger

from .llm_providers import create_vanna_instance, connect_vanna_to_database
from .llm_training import (
    load_training_examples,
    train_on_basic_schema,
    train_on_examples,
)

logger = get_logger(__name__)
llm_logger = get_llm_logger()  # Dedicated LLM log file


class LLMService:
    """
    Service for generating SQL queries from natural language using LLMs.
    
    Supports multiple providers (OpenAI, Anthropic, Ollama) configured via settings.
    Uses Vanna.AI with ChromaDB for training and SQL generation.
    """
    
    def __init__(self):
        """Initialize LLM service with configured provider"""
        self.provider = settings.llm_provider
        self.sql_model = settings.sql_model  # Model for SQL generation
        self.summary_model = settings.summary_model  # Model for summaries
        self.vanna = None
        self._initialized = False
        
        logger.info(f"LLM Service initialized with provider: {self.provider}")
        logger.info(f"  SQL Model (input): {self.sql_model}")
        logger.info(f"  Summary Model (output): {self.summary_model}")
    
    def initialize(self, force_retrain: bool = False) -> None:
        """
        Initialize and train the LLM service.
        
        Args:
            force_retrain: If True, retrain even if already initialized
        """
        if self._initialized and not force_retrain:
            logger.info("LLM Service already initialized")
            return
        
        try:
            # Create Vanna instance for SQL generation
            self.vanna = create_vanna_instance(self.provider, self.sql_model)
            
            # Connect to database
            connect_vanna_to_database(self.vanna)
            
            # Train on basic schema (fast, < 1 second)
            train_on_basic_schema(self.vanna)
            
            # Optionally load and train on examples
            examples = load_training_examples()
            if examples:
                train_on_examples(self.vanna, examples)
                logger.info(f"Loaded {len(examples)} query examples")
            
            self._initialized = True
            
        except Exception as e:
            logger.error(f"Failed to initialize LLM Service: {e}")
            raise
    
    def generate_sql(self, question: str) -> Tuple[str, Optional[str]]:
        """
        Generate SQL query from natural language question.
        
        Args:
            question: Natural language question
        
        Returns:
            Tuple of (sql_query, explanation)
        
        Raises:
            ValueError: If service not initialized, invalid question, or LLM cannot generate SQL
        """
        if not self._initialized:
            raise ValueError("LLM Service not initialized. Call initialize() first.")
        
        if not question or not question.strip():
            raise ValueError("Question cannot be empty")
        
        start_time = time.time()
        
        try:
            logger.info(f"Generating SQL for question: {question}")
            
            # Log the SQL generation request
            llm_logger.info(f"[SQL REQUEST] model={self.sql_model} question={question}")
            
            # Generate SQL using Vanna
            # Note: Vanna internally gathers context (similar questions, DDL, docs) 
            # and constructs the prompt before calling the LLM
            sql = self.vanna.generate_sql(question)
            
            elapsed = time.time() - start_time
            
            # Clean up the SQL (Vanna sometimes wraps it)
            if isinstance(sql, str):
                sql = sql.replace("```sql", "").replace("```", "").strip()
            
            # Validate that the response is actually SQL, not an apology/explanation
            is_valid, error_type = self._validate_sql_response(sql)
            if not is_valid:
                llm_logger.warning(f"[SQL INVALID] time={elapsed:.2f}s type={error_type} response={sql}")
                raise ValueError(self._get_user_friendly_error(error_type, question))
            
            # Log the successful SQL response
            llm_logger.info(f"[SQL RESPONSE] time={elapsed:.2f}s sql={sql}")
            
            # Get explanation (optional)
            explanation = f"This query answers: {question}"
            
            logger.info(f"Generated SQL in {elapsed:.2f}s: {sql[:100]}...")
            return sql, explanation
            
        except ValueError:
            # Re-raise ValueError (our validation errors) as-is
            raise
        except Exception as e:
            elapsed = time.time() - start_time
            llm_logger.error(f"[SQL ERROR] time={elapsed:.2f}s error={str(e)}")
            logger.error(f"Failed to generate SQL: {e}")
            raise
    
    def _validate_sql_response(self, response: str) -> tuple:
        """
        Validate LLM response and categorize any errors.
        
        Args:
            response: The response from the LLM
            
        Returns:
            Tuple of (is_valid: bool, error_type: str or None)
            Error types: 'empty', 'introspection', 'syntax', 'unclear', 'apology', 'invalid_format'
        """
        if not response or not isinstance(response, str):
            return False, 'empty'
        
        response_lower = response.lower().strip()
        
        # Check for Vanna-specific errors first (most specific)
        if "the llm is not allowed" in response_lower or "database introspection" in response_lower:
            return False, 'introspection'
        
        if "error running intermediate sql" in response_lower or "syntax error at or near" in response_lower:
            return False, 'syntax'
        
        # Check for "unclear question" patterns
        unclear_patterns = [
            "not clear", "not actionable", "more details", "clarify",
            "please provide", "could you please", "your request", "your question",
            "doesn't appear"
        ]
        for pattern in unclear_patterns:
            if pattern in response_lower:
                return False, 'unclear'
        
        # Check for apology patterns
        apology_patterns = [
            "i'm sorry", "i'm unable", "i cannot", "i don't",
            "i am sorry", "i am unable", "unfortunately"
        ]
        for pattern in apology_patterns:
            if pattern in response_lower:
                return False, 'apology'
        
        # Check that response starts with valid SQL keywords
        valid_sql_starts = ["select", "with", "-- intermediate_sql"]
        
        # Remove any leading comments for the check
        check_response = response_lower
        while check_response.startswith("--"):
            newline_pos = check_response.find("\n")
            if newline_pos == -1:
                break
            check_response = check_response[newline_pos + 1:].strip()
        
        if not any(check_response.startswith(keyword) for keyword in valid_sql_starts):
            return False, 'invalid_format'
        
        return True, None
    
    def _get_user_friendly_error(self, error_type: str, question: str) -> str:
        """
        Get a user-friendly error message based on the error type.
        
        Args:
            error_type: Type of error ('introspection', 'syntax', 'unclear', 'apology', etc.)
            question: The original question for context
            
        Returns:
            User-friendly error message with suggestions
        """
        if error_type == 'introspection':
            return (
                "Your question requires knowing specific values from the database that I can't look up directly. "
                "Try rephrasing with explicit criteria, for example:\n"
                "- Instead of 'top 10 states', try 'states with the most households'\n"
                "- Instead of 'largest errors', try 'errors ordered by amount'\n"
                "- Use 'ORDER BY ... DESC LIMIT 10' style queries"
            )
        
        if error_type == 'syntax':
            return (
                "There was an issue generating the SQL query. "
                "Please try rephrasing your question more simply, or break it into smaller parts."
            )
        
        if error_type == 'unclear':
            return (
                "I couldn't understand that question clearly. Please try:\n"
                "- Being more specific about what data you want\n"
                "- Using terms like 'count', 'average', 'total', 'by state'\n"
                "- Example: 'How many households are in each state?'"
            )
        
        if error_type == 'apology':
            return (
                "I wasn't able to generate a query for that question. "
                "Please try rephrasing it as a question about your SNAP QC data."
            )
        
        # Default for 'empty', 'invalid_format', or unknown
        return (
            "I couldn't generate a SQL query for that question. "
            "Please try rephrasing it as a question about your SNAP QC data."
        )
    
    def generate_followup_questions(self, question: str, sql: str) -> List[str]:
        """
        Generate followup questions based on the current question and SQL.
        
        Args:
            question: Original question
            sql: Generated SQL query
        
        Returns:
            List of suggested followup questions
        """
        if not self._initialized:
            raise ValueError("LLM Service not initialized. Call initialize() first.")
        
        try:
            # Simple fallback followups
            followups = [
                "What is the average value for this data?",
                "Can you show me the top 10 results?",
                "How does this compare to last year?",
                "What is the breakdown by state?",
            ]
            return followups[:3]
        except Exception as e:
            logger.warning(f"Could not generate followup questions: {e}")
            return []
    
    def generate_text(self, prompt: str, max_tokens: int = 150) -> str:
        """
        Generate text using the SUMMARY MODEL (separate from SQL model).
        
        Args:
            prompt: Text prompt for the LLM
            max_tokens: Maximum tokens to generate
        
        Returns:
            Generated text response
        """
        if not self._initialized:
            self.initialize()
        
        start_time = time.time()
        
        try:
            logger.info(f"Generating text with {self.summary_model} (max_tokens={max_tokens})")
            
            # Log the summary generation request with full prompt
            llm_logger.info(f"[SUMMARY REQUEST] model={self.summary_model} max_tokens={max_tokens} prompt_len={len(prompt)}")
            llm_logger.info(f"[SUMMARY PROMPT FULL]\n{prompt}")
            
            # Use OpenAI directly for summaries to use the summary model
            if self.provider == "openai":
                from openai import OpenAI
                client = OpenAI(api_key=settings.openai_api_key)
                
                response = client.chat.completions.create(
                    model=self.summary_model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=max_tokens,
                    temperature=0.3
                )
                
                elapsed = time.time() - start_time
                
                if response.choices and response.choices[0].message.content:
                    result = response.choices[0].message.content.strip()
                    llm_logger.info(f"[SUMMARY RESPONSE] time={elapsed:.2f}s response_len={len(result)}")
                    llm_logger.info(f"[SUMMARY RESPONSE FULL]\n{result}")
                    return result
                else:
                    llm_logger.warning(f"[SUMMARY EMPTY] time={elapsed:.2f}s")
                    logger.warning("Empty response from OpenAI")
                    return "Unable to generate summary."
                    
            else:
                # For other providers, use Vanna (will use SQL model)
                response = self.vanna.submit_prompt(prompt, kwargs={"max_tokens": max_tokens})
                
                elapsed = time.time() - start_time
                
                if response:
                    result = response.strip()
                    llm_logger.info(f"[SUMMARY RESPONSE] time={elapsed:.2f}s response_len={len(result)}")
                    llm_logger.info(f"[SUMMARY RESPONSE FULL]\n{result}")
                    return result
                else:
                    llm_logger.warning(f"[SUMMARY EMPTY] time={elapsed:.2f}s")
                    return "Unable to generate summary."
                
        except Exception as e:
            elapsed = time.time() - start_time
            llm_logger.error(f"[SUMMARY ERROR] time={elapsed:.2f}s error={str(e)}")
            logger.error(f"Error generating text: {e}", exc_info=True)
            return "Unable to generate summary."
    
    def get_provider_info(self) -> Dict:
        """Get information about the current LLM provider and configuration"""
        status_text = "Ready (lazy init)" if not self._initialized else "Initialized"
        
        return {
            "provider": self.provider,
            "sql_model": self.sql_model,
            "sql_max_tokens": settings.effective_sql_max_tokens,
            "sql_temperature": settings.effective_sql_temperature,
            "summary_model": self.summary_model,
            "summary_max_tokens": settings.llm_summary_max_tokens,
            "summary_max_prompt_size": settings.llm_summary_max_prompt_size,
            "temperature": settings.llm_temperature,
            "max_tokens": settings.llm_max_tokens,
            "initialized": self._initialized,
            "status": status_text,
            "training_enabled": settings.vanna_training_enabled,
        }
    
    def check_health(self) -> Dict:
        """
        Check LLM provider health/availability.
        
        Verifies:
        - OpenAI: API key is configured
        - Anthropic: API key is configured
        - Ollama: Server is reachable
        
        Returns:
            Dict with 'healthy', 'provider', 'status', and optional 'error' keys
        """
        result = {
            "provider": self.provider.upper(),
            "healthy": False,
            "status": "unknown",
            "model": self.sql_model,
        }
        
        try:
            if self.provider == "openai":
                # Check if API key is configured
                if not settings.openai_api_key:
                    result["status"] = "not_configured"
                    result["error"] = "OPENAI_API_KEY not set"
                    return result
                
                # Try a minimal API call to verify the key works
                try:
                    from openai import OpenAI
                    client = OpenAI(api_key=settings.openai_api_key)
                    # List models is a lightweight way to verify the key
                    client.models.list()
                    result["healthy"] = True
                    result["status"] = "connected"
                except Exception as e:
                    result["status"] = "connection_failed"
                    result["error"] = str(e)
                    
            elif self.provider == "anthropic":
                # Check if API key is configured
                if not settings.anthropic_api_key:
                    result["status"] = "not_configured"
                    result["error"] = "ANTHROPIC_API_KEY not set"
                    return result
                
                # For Anthropic, just verify key format (starts with sk-ant-)
                if settings.anthropic_api_key.startswith("sk-ant-"):
                    result["healthy"] = True
                    result["status"] = "configured"
                else:
                    result["status"] = "invalid_key_format"
                    result["error"] = "API key doesn't match expected format"
                    
            elif self.provider == "ollama":
                # Check if Ollama server is reachable
                import httpx
                
                try:
                    with httpx.Client(timeout=5.0) as client:
                        # Check Ollama's /api/tags endpoint (lists models)
                        response = client.get(f"{settings.ollama_base_url}/api/tags")
                        if response.status_code == 200:
                            models = response.json().get("models", [])
                            model_names = [m.get("name", "") for m in models]
                            
                            # Check if our configured model is available
                            if any(self.sql_model in name for name in model_names):
                                result["healthy"] = True
                                result["status"] = "connected"
                                result["available_models"] = model_names[:5]  # Show first 5
                            else:
                                result["status"] = "model_not_found"
                                result["error"] = f"Model '{self.sql_model}' not found. Available: {model_names[:3]}"
                        else:
                            result["status"] = "server_error"
                            result["error"] = f"Server returned {response.status_code}"
                except httpx.ConnectError:
                    result["status"] = "not_reachable"
                    result["error"] = f"Cannot connect to Ollama at {settings.ollama_base_url}"
                except Exception as e:
                    result["status"] = "connection_failed"
                    result["error"] = str(e)
            else:
                result["status"] = "unknown_provider"
                result["error"] = f"Unknown provider: {self.provider}"
                
        except Exception as e:
            logger.error(f"LLM health check failed: {e}")
            result["status"] = "error"
            result["error"] = str(e)
        
        return result


# =============================================================================
# GLOBAL SERVICE INSTANCE
# =============================================================================

_llm_service: Optional[LLMService] = None


def get_llm_service() -> LLMService:
    """
    Get the global LLM service instance (singleton pattern).
    
    Returns:
        LLMService instance
    """
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service


def initialize_llm_service(force_retrain: bool = False) -> None:
    """
    Initialize the global LLM service.
    
    Args:
        force_retrain: If True, retrain even if already initialized
    """
    service = get_llm_service()
    service.initialize(force_retrain=force_retrain)
