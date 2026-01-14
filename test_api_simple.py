#!/usr/bin/env python3
"""
Quick API test without LLM initialization
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvic

app = FastAPI(title="Test API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/api/v1/filter/")
async def get_filter():
    return {"filter": {"state": None, "fiscal_year": None}}

@app.post("/api/v1/filter/set")
async def set_filter(request: dict):
    return {"status": "success", "filter": request}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
