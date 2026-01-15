"""
LLM Provider Classes

Vanna implementations for different LLM providers (OpenAI, Anthropic, Ollama).
Each class combines ChromaDB vector store with a specific LLM backend.
"""

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


def create_vanna_instance(provider: str, model: str):
    """
    Create a Vanna instance for the specified provider.
    
    Args:
        provider: LLM provider name (openai, anthropic, ollama)
        model: Model name to use
        
    Returns:
        Configured Vanna instance
        
    Raises:
        ValueError: If provider is unsupported or missing API key
    """
    config = {
        "model": model,
        "temperature": settings.llm_temperature,
        "max_tokens": settings.llm_max_tokens,
        "path": settings.vanna_chromadb_path,
    }
    
    if provider == "openai":
        if not settings.openai_api_key:
            raise ValueError("OpenAI API key not configured. Set OPENAI_API_KEY in .env")
        config["api_key"] = settings.openai_api_key
        logger.info(f"Creating Vanna with OpenAI ({model}) and ChromaDB")
        return VannaOpenAI(config=config)
    
    elif provider == "anthropic":
        if not settings.anthropic_api_key:
            raise ValueError("Anthropic API key not configured. Set ANTHROPIC_API_KEY in .env")
        config["api_key"] = settings.anthropic_api_key
        logger.info(f"Creating Vanna with Anthropic Claude ({model}) and ChromaDB")
        return VannaAnthropic(config=config)
    
    elif provider == "ollama":
        config["host"] = settings.ollama_base_url
        logger.info(f"Creating Vanna with Ollama ({model} at {settings.ollama_base_url}) and ChromaDB")
        return VannaOllama(config=config)
    
    else:
        raise ValueError(f"Unsupported LLM provider: {provider}")


def connect_vanna_to_database(vanna_instance):
    """
    Connect a Vanna instance to the PostgreSQL database.
    
    Args:
        vanna_instance: Vanna instance to connect
        
    Returns:
        True if connected successfully, False otherwise
    """
    try:
        vanna_instance.connect_to_postgres(
            host="localhost",
            dbname="snapanalyst_db",
            user="snapanalyst",
            password="snapanalyst_dev_password",
            port=5432
        )
        logger.info("Connected Vanna to PostgreSQL database")
        return True
    except Exception as e:
        logger.warning(f"Could not connect Vanna to database: {e}")
        return False
