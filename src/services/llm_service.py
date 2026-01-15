"""
LLM Service for Natural Language to SQL Query Generation

Supports multiple LLM providers:
- OpenAI (GPT-4)
- Anthropic (Claude)
- Ollama (Local models)

Uses Vanna.AI with ChromaDB for SQL generation with training data.
"""
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from vanna.chromadb import ChromaDB_VectorStore
from vanna.openai import OpenAI_Chat
from vanna.anthropic import Anthropic_Chat
from vanna.ollama import Ollama

from src.core.config import settings
from src.core.logging import get_logger

logger = get_logger(__name__)


class VannaOpenAI(ChromaDB_VectorStore, OpenAI_Chat):
    """Vanna implementation with OpenAI and ChromaDB vector store"""
    def __init__(self, config=None):
        ChromaDB_VectorStore.__init__(self, config=config)
        OpenAI_Chat.__init__(self, config=config)


class VannaAnthropic(ChromaDB_VectorStore, Anthropic_Chat):
    """Vanna implementation with Anthropic Claude and ChromaDB vector store"""
    def __init__(self, config=None):
        ChromaDB_VectorStore.__init__(self, config=config)
        Anthropic_Chat.__init__(self, config=config)


class VannaOllama(ChromaDB_VectorStore, Ollama):
    """Vanna implementation with Ollama and ChromaDB vector store"""
    def __init__(self, config=None):
        ChromaDB_VectorStore.__init__(self, config=config)
        Ollama.__init__(self, config=config)


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
        self.vanna_summary = None  # Separate instance for summaries
        self._initialized = False
        
        logger.info(f"LLM Service initialized with provider: {self.provider}")
        logger.info(f"  SQL Model (input): {self.sql_model}")
        logger.info(f"  Summary Model (output): {self.summary_model}")
    
    def _initialize_vanna(self, model: str = None):
        """Initialize Vanna with the configured LLM provider and ChromaDB
        
        Args:
            model: Optional model override. If not provided, uses self.sql_model
        """
        config = {
            "model": model or self.sql_model,
            "temperature": settings.llm_temperature,
            "max_tokens": settings.llm_max_tokens,
        }
        
        if self.provider == "openai":
            if not settings.openai_api_key:
                raise ValueError("OpenAI API key not configured. Set OPENAI_API_KEY in .env")
            config["api_key"] = settings.openai_api_key
            logger.info(f"Initializing Vanna with OpenAI ({config['model']}) and ChromaDB")
            return VannaOpenAI(config=config)
        
        elif self.provider == "anthropic":
            if not settings.anthropic_api_key:
                raise ValueError("Anthropic API key not configured. Set ANTHROPIC_API_KEY in .env")
            config["api_key"] = settings.anthropic_api_key
            logger.info(f"Initializing Vanna with Anthropic Claude ({config['model']}) and ChromaDB")
            return VannaAnthropic(config=config)
        
        elif self.provider == "ollama":
            config["host"] = settings.ollama_base_url
            logger.info(f"Initializing Vanna with Ollama ({config['model']} at {settings.ollama_base_url}) and ChromaDB")
            return VannaOllama(config=config)
        
        else:
            raise ValueError(f"Unsupported LLM provider: {self.provider}")
    
    def _load_schema(self) -> Dict:
        """Load database schema documentation"""
        schema_path = Path(settings.vanna_schema_path)
        if not schema_path.exists():
            raise FileNotFoundError(f"Schema file not found: {schema_path}")
        
        with open(schema_path, 'r') as f:
            schema = json.load(f)
        
        logger.info(f"Loaded schema from {schema_path}")
        return schema
    
    def _load_training_examples(self) -> List[Dict]:
        """Load SQL query examples for training"""
        examples_path = Path(settings.vanna_training_data_path)
        if not examples_path.exists():
            logger.warning(f"Training examples file not found: {examples_path}")
            return []
        
        with open(examples_path, 'r') as f:
            data = json.load(f)
        
        examples = data.get('example_queries', [])
        logger.info(f"Loaded {len(examples)} training examples from {examples_path}")
        return examples
    
    def _train_on_schema(self, schema: Dict) -> None:
        """Train Vanna on database schema"""
        logger.info("Training Vanna on database schema...")
        
        # Train on table structures
        for table_name, table_info in schema['tables'].items():
            ddl = self._generate_ddl_from_schema(table_name, table_info)
            self.vanna.train(ddl=ddl)
            logger.debug(f"Trained on table: {table_name}")
        
        # Train on documentation
        db_doc = (
            f"Database: {schema['database']['name']}\n"
            f"Description: {schema['database']['description']}\n"
            f"Purpose: {schema['database']['purpose']}\n"
        )
        self.vanna.train(documentation=db_doc)
        
        logger.info("Schema training completed")
    
    def _generate_ddl_from_schema(self, table_name: str, table_info: Dict) -> str:
        """Generate DDL statement from schema definition"""
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
    
    def _train_on_examples(self, examples: List[Dict]) -> None:
        """Train Vanna on example queries"""
        logger.info(f"Training Vanna on {len(examples)} query examples...")
        
        trained_count = 0
        for example in examples:
            question = example.get('question')
            sql = example.get('sql')
            
            if question and sql:
                try:
                    self.vanna.train(question=question, sql=sql)
                    trained_count += 1
                except Exception as e:
                    logger.warning(f"Failed to train on example: {question[:50]}... - {e}")
        
        logger.info(f"Successfully trained on {trained_count} examples")
    
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
            # Initialize Vanna with configured provider
            self.vanna = self._initialize_vanna()
            
            if settings.vanna_training_enabled or force_retrain:
                # Load and train on schema
                schema = self._load_schema()
                self._train_on_schema(schema)
                
                # Load and train on examples
                examples = self._load_training_examples()
                if examples:
                    self._train_on_examples(examples)
                
                logger.info("✅ LLM Service training completed successfully")
            else:
                logger.info("Training disabled, using pre-trained model")
            
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
            ValueError: If service not initialized or invalid question
        """
        if not self._initialized:
            raise ValueError("LLM Service not initialized. Call initialize() first.")
        
        if not question or not question.strip():
            raise ValueError("Question cannot be empty")
        
        try:
            logger.info(f"Generating SQL for question: {question}")
            
            # Generate SQL using Vanna
            sql = self.vanna.generate_sql(question)
            
            # Clean up the SQL (Vanna sometimes wraps it)
            if isinstance(sql, str):
                # Remove markdown code blocks if present
                sql = sql.replace("```sql", "").replace("```", "").strip()
            
            # Get explanation (optional)
            explanation = None
            try:
                # Vanna can generate explanations in some cases
                explanation = f"This query answers: {question}"
            except Exception as e:
                logger.warning(f"Could not generate explanation: {e}")
            
            logger.info(f"Generated SQL: {sql[:100]}...")
            return sql, explanation
            
        except Exception as e:
            logger.error(f"Failed to generate SQL: {e}")
            raise
    
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
            # Vanna has a method for this, but let's provide a simple fallback
            followups = [
                "What is the average value for this data?",
                "Can you show me the top 10 results?",
                "How does this compare to last year?",
                "What is the breakdown by state?",
            ]
            return followups[:3]  # Return top 3
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
        
        try:
            logger.info(f"Generating text with {self.summary_model} (max_tokens={max_tokens})")
            
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
                
                if response.choices and response.choices[0].message.content:
                    return response.choices[0].message.content.strip()
                else:
                    logger.warning("Empty response from OpenAI")
                    return "Unable to generate summary."
                    
            else:
                # For other providers, use Vanna (will use SQL model)
                response = self.vanna.submit_prompt(prompt, kwargs={"max_tokens": max_tokens})
                
                if response:
                    return response.strip()
                else:
                    return "Unable to generate summary."
                
        except Exception as e:
            logger.error(f"Error generating text: {e}", exc_info=True)
            return "Unable to generate summary."
    
    def get_provider_info(self) -> Dict:
        """Get information about the current LLM provider and configuration"""
        # Check if we can generate text (lazy initialization)
        status_text = "Ready (lazy init)" if not self._initialized else "Initialized"
        
        return {
            "provider": self.provider,
            "sql_model": self.sql_model,
            "summary_model": self.summary_model,
            "temperature": settings.llm_temperature,
            "max_tokens": settings.llm_max_tokens,
            "initialized": self._initialized,
            "status": status_text,
            "training_enabled": settings.vanna_training_enabled,
        }


# Global LLM service instance
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
