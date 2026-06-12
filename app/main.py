"""
RAG AI System - Main Entry Point
Handles application lifecycle (Lifespan), Middleware, Routing, and Static Assets.
"""

import os
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.routing import APIRoute

# --- Core Logic & Config ---
from app.brain.vector_service import vector_store
from app.config import UPLOAD_DIR, APP_NAME, EMBEDDING_MODEL, OPENAI_API_KEY

# --- API Routers ---
from app.routers import (
    upload_router, 
    query_router, 
    document_router, 
)

# Logging Setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# =========================================================
# 🔄 LIFESPAN (Startup & Shutdown Logic)
# =========================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ------------------ STARTUP ------------------
    print(f"\n{'='*40}")
    print(f"🚀 {APP_NAME} INITIALIZING")
    print(f"{'='*40}")

    if not OPENAI_API_KEY:
        logger.error("❌ CRITICAL: OpenAI API Key missing from environment.")

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    os.makedirs("deliverables", exist_ok=True)
    
    try:
        vector_store.load_index()
        logger.info("✅ Vector index successfully restored from disk.")
    except Exception as e:
        logger.warning(f"⚠️ No index found or load failed: {e}. Starting fresh.")

    logger.info(f"System active using model: {EMBEDDING_MODEL}")
    yield 

    # ------------------ SHUTDOWN ------------------
    logger.info("💾 Persistence: Saving vector index before shutdown...")
    try:
        vector_store.save_index()
    except Exception as e:
        logger.error(f"❌ Failed to save index: {e}")

# =========================================================
# 🏗️ INITIALIZE FASTAPI APP
# =========================================================
app = FastAPI(
    title=APP_NAME, 
    description="AI-Driven RAG Analysis & Document Intelligence System",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================================================
# 🔌 ROUTER REGISTRATION (FIXED PREFIX)
# =========================================================
# Mapping these to /api ensures your fetch("/api/upload/bundle") works!
app.include_router(upload_router.router, prefix="/api")
app.include_router(query_router.router, prefix="/api")
app.include_router(document_router.router, prefix="/api")

# Diagnostic check
for route in app.routes:
    if isinstance(route, APIRoute):
        print(f"✅ Registered: {list(route.methods)} {route.path}")

# =========================================================
# 📁 STATIC FILES & UI
# =========================================================
if os.path.exists("app/web"):
    app.mount("/static", StaticFiles(directory="app/web"), name="static")
    
@app.get("/", tags=["Frontend"])
async def serve_frontend():
    return FileResponse("app/web/index.html")