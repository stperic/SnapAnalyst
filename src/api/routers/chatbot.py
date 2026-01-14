"""
Chatbot API Router - Natural Language Query Interface

Provides endpoints for conversational SQL query generation using LLMs.
"""
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from src.core.logging import get_logger
from src.services.llm_service import get_llm_service, initialize_llm_service
from src.api.routers.query import execute_sql_query, SQLQueryRequest

logger = get_logger(__name__)


router = APIRouter()


# ============================================================================
# Request/Response Models
# ============================================================================


class ChatQueryRequest(BaseModel):
    """Request model for natural language query"""
    
    question: str = Field(
        ...,
        min_length=3,
        max_length=500,
        description="Natural language question about SNAP QC data",
        examples=["How many households received SNAP benefits in 2023?"]
    )
    execute: bool = Field(
        default=True,
        description="If True, execute the generated SQL and return results"
    )
    explain: bool = Field(
        default=True,
        description="If True, include explanation of the generated SQL"
    )


class TextGenerationRequest(BaseModel):
    """Request model for general text generation"""
    
    prompt: str = Field(
        ...,
        min_length=10,
        max_length=2000,
        description="Text prompt for the LLM"
    )
    max_tokens: int = Field(
        default=150,
        ge=10,
        le=500,
        description="Maximum tokens to generate"
    )


class TextGenerationResponse(BaseModel):
    """Response model for text generation"""
    
    text: str = Field(..., description="Generated text")
    tokens_used: Optional[int] = Field(None, description="Approximate tokens used")


class ChatQueryResponse(BaseModel):
    """Response model for natural language query"""
    
    question: str = Field(..., description="Original question")
    sql: str = Field(..., description="Generated SQL query")
    explanation: Optional[str] = Field(None, description="Explanation of the SQL query")
    executed: bool = Field(..., description="Whether the query was executed")
    results: Optional[List[Dict]] = Field(None, description="Query results (if executed)")
    row_count: Optional[int] = Field(None, description="Number of rows returned")
    followup_questions: Optional[List[str]] = Field(None, description="Suggested followup questions")
    provider: str = Field(..., description="LLM provider used (openai/anthropic/ollama)")
    model: str = Field(..., description="LLM model used")


class ProviderInfoResponse(BaseModel):
    """Response model for LLM provider information"""
    
    provider: str = Field(..., description="Current LLM provider")
    model: str = Field(..., description="Current LLM model")
    temperature: float = Field(..., description="LLM temperature setting")
    max_tokens: int = Field(..., description="Maximum tokens for LLM response")
    initialized: bool = Field(..., description="Whether service is initialized")
    training_enabled: bool = Field(..., description="Whether training is enabled")


class TrainingStatusResponse(BaseModel):
    """Response model for training status"""
    
    status: str = Field(..., description="Training status")
    message: str = Field(..., description="Status message")


# ============================================================================
# Endpoints
# ============================================================================


@router.post(
    "/query",
    response_model=ChatQueryResponse,
    status_code=status.HTTP_200_OK,
    summary="Ask a question in natural language",
    description="Convert natural language question to SQL and optionally execute it",
    response_description="Generated SQL query and optional results",
)
async def chat_query(request: ChatQueryRequest) -> ChatQueryResponse:
    """
    Convert natural language question to SQL query using LLM.
    
    This endpoint uses the configured LLM (OpenAI/Anthropic/Ollama) to:
    1. Convert your question to a SQL query
    2. Optionally execute the query
    3. Provide an explanation of the SQL
    4. Suggest followup questions
    
    **Examples:**
    - "How many households received SNAP in 2023?"
    - "What's the average benefit amount by state?"
    - "Show me households with children and income over $2000"
    - "What are the most common error types?"
    
    **Configuration:**
    Set these environment variables:
    - `LLM_PROVIDER`: openai, anthropic, or ollama
    - `OPENAI_API_KEY`: If using OpenAI
    - `ANTHROPIC_API_KEY`: If using Anthropic
    - `OLLAMA_BASE_URL`: If using Ollama (default: http://localhost:11434)
    """
    try:
        # Get LLM service
        llm_service = get_llm_service()
        
        # Ensure service is initialized
        if not llm_service._initialized:
            logger.info("LLM service not initialized, initializing now...")
            initialize_llm_service()
        
        # Generate SQL from question
        sql, explanation = llm_service.generate_sql(request.question)
        
        if not sql:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Could not generate SQL from the question. Please rephrase."
            )
        
        # Debug: Log SQL before filter
        logger.info(f"SQL before filter: {sql}")
        
        # Apply global filter to generated SQL
        from src.core.filter_manager import get_filter_manager
        filter_manager = get_filter_manager()
        sql_after_filter = filter_manager.apply_to_sql(sql)
        
        # Debug: Log SQL after filter
        logger.info(f"SQL after filter: {sql_after_filter}")
        sql = sql_after_filter
        
        # Get provider info
        provider_info = llm_service.get_provider_info()
        
        # Execute query if requested
        results = None
        row_count = None
        if request.execute:
            try:
                sql_request = SQLQueryRequest(sql=sql)
                query_response = await execute_sql_query(sql_request)
                # Pass data as list of dictionaries (as expected by response model)
                results = query_response.data
                row_count = query_response.row_count
            except Exception as e:
                logger.error(f"Failed to execute generated SQL: {e}")
                # Don't fail the whole request, just note execution failed
                results = None
                row_count = 0
        
        # Generate followup questions (optional)
        followup_questions = None
        if request.explain:
            try:
                followup_questions = llm_service.generate_followup_questions(
                    request.question, sql
                )
            except Exception as e:
                logger.warning(f"Could not generate followup questions: {e}")
        
        return ChatQueryResponse(
            question=request.question,
            sql=sql,
            explanation=explanation if request.explain else None,
            executed=request.execute,
            results=results,
            row_count=row_count,
            followup_questions=followup_questions,
            provider=provider_info["provider"],
            model=provider_info["sql_model"],  # Use SQL model for query generation
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Chat query failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process question: {str(e)}"
        )


@router.get(
    "/provider",
    response_model=ProviderInfoResponse,
    status_code=status.HTTP_200_OK,
    summary="Get LLM provider information",
    description="Returns information about the currently configured LLM provider",
)
async def get_provider_info() -> ProviderInfoResponse:
    """
    Get information about the configured LLM provider.
    
    Returns details about which LLM is being used (OpenAI, Anthropic, Ollama),
    the model name, and configuration settings.
    """
    try:
        llm_service = get_llm_service()
        info = llm_service.get_provider_info()
        return ProviderInfoResponse(**info)
    except Exception as e:
        logger.error(f"Failed to get provider info: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post(
    "/train",
    response_model=TrainingStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrain the LLM service",
    description="Force retrain the LLM on schema and example queries",
)
async def retrain_service() -> TrainingStatusResponse:
    """
    Force retrain the LLM service on schema and example queries.
    
    This will:
    1. Reload the database schema from data_mapping.json
    2. Reload query examples from query_examples.json
    3. Retrain the LLM with updated information
    
    Use this after updating schema documentation or adding new query examples.
    """
    try:
        logger.info("Starting LLM service retraining...")
        initialize_llm_service(force_retrain=True)
        
        return TrainingStatusResponse(
            status="success",
            message="LLM service retrained successfully"
        )
    except Exception as e:
        logger.error(f"Failed to retrain service: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrain: {str(e)}"
        )


@router.get(
    "/examples",
    response_model=List[str],
    status_code=status.HTTP_200_OK,
    summary="Get example questions",
    description="Returns a list of example questions you can ask",
)
async def get_example_questions() -> List[str]:
    """
    Get example questions to help users understand what they can ask.
    
    Returns a curated list of example questions from the training data.
    """
    examples = [
        "How many households received SNAP benefits in 2023?",
        "What is the average SNAP benefit amount by state?",
        "Show me the top 10 states by total SNAP recipients",
        "How many households have children under 5?",
        "What percentage of households are elderly?",
        "What are the most common error types in QC reviews?",
        "Show me households with income between $1000 and $2000",
        "How many households received expedited service?",
        "What is the average household size by region?",
        "Show me error rates by state",
        "How many households have disabled members?",
        "What is the distribution of SNAP benefits by household composition?",
        "Show me households with overissuance errors",
        "What percentage of households pass all income tests?",
        "How many households receive the minimum benefit?",
    ]
    return examples


@router.post(
    "/generate-text",
    response_model=TextGenerationResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate text using LLM",
    description="Generate text response for a given prompt (not SQL-specific)",
)
async def generate_text_endpoint(request: TextGenerationRequest):
    """Generate text using the configured LLM"""
    try:
        llm_service = get_llm_service()
        if not llm_service._initialized:
            initialize_llm_service()
            llm_service = get_llm_service()
        
        generated_text = llm_service.generate_text(request.prompt, request.max_tokens)
        
        return TextGenerationResponse(
            text=generated_text,
            tokens_used=request.max_tokens
        )
    except Exception as e:
        logger.error(f"Error generating text: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate text: {str(e)}"
        )

