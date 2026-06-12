"""
RFQ AI System - Query & Search Router
Handles direct AI questions (Standard & Agentic) and raw document search/retrieval operations.
"""

import logging
from typing import List, Dict, Optional, Any
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

# --- Core Pipelines & Logic ---
from app.pipeline.query_pipeline import ask_rfq, search_documents
from app.brain.llm_service import run_agent_loop
from app.pipeline.optimization_service import retrieve_and_rerank

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/query", tags=["Query & Search"])

# ==========================================
# 📝 PYDANTIC MODELS
# ==========================================
class QueryRequest(BaseModel):
    question: str = Field(..., min_length=2)

class AgentRequest(BaseModel):
    query: str = Field(..., min_length=2)

class RAGQueryResponse(BaseModel):
    question: str
    answer: str
    sources: List[str] = []
    chunks_used: int = 0
    confidence: float = 0.0
    context_preview: str = ""
    error: Optional[str] = None

class AgentResponse(BaseModel):
    answer: Optional[str] = None

class SearchRequest(BaseModel):
    query: str = Field(..., min_length=2)
    initial_k: int = Field(default=20, ge=1, le=100)
    final_k: int = Field(default=5, ge=1, le=30)

class SearchResponse(BaseModel):
    status: str
    query: str
    results: List[Dict[str, Any]]
    confidence_score: float

# ==========================================
# 🤖 1. STANDARD CHATBOT ENDPOINT (/ask)
# ==========================================
@router.post("/ask", response_model=RAGQueryResponse, summary="Ask the RAG System")
async def query_rfq(request: QueryRequest):
    try:
        logger.info(f"🤖 Processing standard user query: '{request.question}'")
        result = await ask_rfq(question=request.question)
        
        if result.get("error"):
            raise HTTPException(status_code=500, detail=result["error"])
            
        return RAGQueryResponse(**result)

    except Exception as e:
        logger.error(f"❌ API Query Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="The AI query failed to process.")

# ==========================================
# 🧠 2. AGENTIC REASONING ENDPOINT (/agent)
# ==========================================
@router.post("/agent", response_model=AgentResponse, summary="Trigger AI Agent Reasoning")
async def ask_agent(request: AgentRequest):
    logger.info(f"📩 Received Agent Query: '{request.query}'")
    try:
        agent_response = await run_agent_loop(request.query)
        return AgentResponse(answer=agent_response)
    except Exception as e:
        logger.error(f"❌ Agent Router Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="The Agent encountered a processing error.")

# ==========================================
# 🔍 3. RAW SEARCH ENDPOINT (/search)
# ==========================================
@router.post("/search", response_model=SearchResponse, summary="Raw Vector Search & Rerank")
async def search_documents_endpoint(request: SearchRequest):
    """
    Consolidated search endpoint. Executes hybrid search + reranking.
    """
    logger.info(f"🔍 Executing search for query: '{request.query}'")
    try:
        results, score = await retrieve_and_rerank(
            query=request.query,
            initial_k=request.initial_k,
            final_k=request.final_k
        )
        return SearchResponse(
            status="success",
            query=request.query,
            results=results,
            confidence_score=score
        )
    except Exception as e:
        logger.error(f"❌ Search routing failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Search execution failed.")