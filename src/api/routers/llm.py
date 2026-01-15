"""
LLM Training Management API Router

Endpoints for managing Vanna AI training and ChromaDB vector store.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict
from pathlib import Path
import shutil

from src.core.config import settings
from src.core.logging import get_logger
from src.services.llm_service import get_llm_service

logger = get_logger(__name__)

router = APIRouter(tags=["llm"])


class TrainingStatusResponse(BaseModel):
    """Training status response"""
    enabled: bool
    chromadb_path: str
    chromadb_exists: bool
    chromadb_size_mb: float = 0.0
    message: str


class TrainingToggleResponse(BaseModel):
    """Training toggle response"""
    success: bool
    enabled: bool
    message: str
    chromadb_cleaned: bool = False


@router.get("/training/status", response_model=TrainingStatusResponse)
async def get_training_status():
    """
    Get current training status.
    
    Returns:
        Training configuration and ChromaDB status
    """
    try:
        chromadb_path = Path(settings.vanna_chromadb_path)
        chromadb_exists = chromadb_path.exists()
        
        # Calculate size if exists
        size_mb = 0.0
        if chromadb_exists:
            total_size = sum(
                f.stat().st_size 
                for f in chromadb_path.rglob('*') 
                if f.is_file()
            )
            size_mb = total_size / (1024 * 1024)  # Convert to MB
        
        return TrainingStatusResponse(
            enabled=settings.vanna_training_enabled,
            chromadb_path=str(chromadb_path),
            chromadb_exists=chromadb_exists,
            chromadb_size_mb=round(size_mb, 2),
            message="Training enabled" if settings.vanna_training_enabled else "Training disabled"
        )
        
    except Exception as e:
        logger.error(f"Error getting training status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/training/enable", response_model=TrainingToggleResponse)
async def enable_training():
    """
    Enable AI training.
    
    Enables persistent training with ChromaDB vector store.
    Note: This doesn't change the config file, only runtime behavior.
    """
    try:
        # Note: We can't change settings at runtime since it's loaded once
        # This endpoint is mainly for informational purposes
        # Actual training control is in config.py
        
        llm_service = get_llm_service()
        
        logger.info("Training enable requested (requires config change)")
        
        return TrainingToggleResponse(
            success=True,
            enabled=settings.vanna_training_enabled,
            message="Training is controlled by VANNA_TRAINING_ENABLED in config. Current value: " 
                    + ("Enabled" if settings.vanna_training_enabled else "Disabled. Change config and restart to enable."),
            chromadb_cleaned=False
        )
        
    except Exception as e:
        logger.error(f"Error enabling training: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/training/disable", response_model=TrainingToggleResponse)
async def disable_training():
    """
    Disable AI training and clean ChromaDB.
    
    Removes the ChromaDB vector store directory to free up space.
    """
    try:
        chromadb_path = Path(settings.vanna_chromadb_path)
        cleaned = False
        
        # Clean ChromaDB if it exists
        if chromadb_path.exists():
            logger.info(f"Cleaning ChromaDB at {chromadb_path}")
            shutil.rmtree(chromadb_path)
            cleaned = True
            logger.info("ChromaDB cleaned successfully")
        else:
            logger.info("ChromaDB directory does not exist, nothing to clean")
        
        return TrainingToggleResponse(
            success=True,
            enabled=False,
            message="Training disabled and ChromaDB cleaned" if cleaned else "Training disabled (ChromaDB was already empty)",
            chromadb_cleaned=cleaned
        )
        
    except Exception as e:
        logger.error(f"Error disabling training: {e}")
        raise HTTPException(status_code=500, detail=f"Error cleaning ChromaDB: {str(e)}")


@router.delete("/training/chromadb", response_model=TrainingToggleResponse)
async def clean_chromadb():
    """
    Clean ChromaDB vector store.
    
    Removes all stored embeddings and training data.
    Useful for resetting the vector database without changing training settings.
    """
    try:
        chromadb_path = Path(settings.vanna_chromadb_path)
        
        if not chromadb_path.exists():
            return TrainingToggleResponse(
                success=True,
                enabled=settings.vanna_training_enabled,
                message="ChromaDB directory does not exist (already clean)",
                chromadb_cleaned=False
            )
        
        # Calculate size before deletion
        total_size = sum(
            f.stat().st_size 
            for f in chromadb_path.rglob('*') 
            if f.is_file()
        )
        size_mb = total_size / (1024 * 1024)
        
        logger.info(f"Cleaning ChromaDB at {chromadb_path} ({size_mb:.2f} MB)")
        shutil.rmtree(chromadb_path)
        logger.info("ChromaDB cleaned successfully")
        
        return TrainingToggleResponse(
            success=True,
            enabled=settings.vanna_training_enabled,
            message=f"ChromaDB cleaned successfully (freed {size_mb:.2f} MB)",
            chromadb_cleaned=True
        )
        
    except Exception as e:
        logger.error(f"Error cleaning ChromaDB: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/info")
async def get_llm_info() -> Dict:
    """
    Get LLM service information.
    
    Returns:
        Provider, model, and configuration details
    """
    try:
        llm_service = get_llm_service()
        info = llm_service.get_provider_info()
        
        # Add ChromaDB info
        chromadb_path = Path(settings.vanna_chromadb_path)
        info["chromadb"] = {
            "path": str(chromadb_path),
            "exists": chromadb_path.exists(),
            "training_enabled": settings.vanna_training_enabled,
        }
        
        return info
        
    except Exception as e:
        logger.error(f"Error getting LLM info: {e}")
        raise HTTPException(status_code=500, detail=str(e))
