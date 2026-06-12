import logging
import re
import aiofiles
from pathlib import Path
from uuid import uuid4
from typing import List
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status
from pydantic import BaseModel

# --- Internal Services ---
from app.pipeline.rag_pipeline import process_rfq, process_rfq_bundle
from app.models.rfq_model import RFQRequest, RFQResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/upload", tags=["Upload & Process"])

# Setup Upload Directory using Pathlib
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# --- Models ---
class SearchRequest(BaseModel):
    query: str

# ---------------------------------------------------------
# 🧹 HELPER: Filename Sanitizer
# ---------------------------------------------------------
def sanitize_filename(filename: str) -> str:
    """Removes spaces and special characters from uploaded filenames to prevent file system errors."""
    if not filename:
        return f"uploaded_{uuid4().hex}.bin"
    # Keep alphanumeric, dots, hyphens, and underscores
    clean_name = re.sub(r'[^a-zA-Z0-9.\-_]', '_', filename)
    # Strip trailing/leading underscores that might have been created by the regex
    return clean_name.strip('_')

# ---------------------------------------------------------
# 1️⃣ SINGLE FILE PROCESSING
# ---------------------------------------------------------
@router.post("/process", response_model=RFQResponse, summary="Process Single Document")
async def process_single_rfq(request: RFQRequest):
    """
    Processes a single document already present on the server.
    Ideal for re-running analysis on a specific file.
    """
    try:
        file_path = request.file_path
        logger.info(f"Processing single file: {file_path}")

        result = await process_rfq(file_path)

        if result.get("status") == "error":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail=result.get("message", "Unknown extraction error.")
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Single-file processing failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail="An error occurred while processing the file."
        )

# ---------------------------------------------------------
# 2️⃣ MULTI-FILE BUNDLE UPLOAD (Document Intelligence Task)
# ---------------------------------------------------------
@router.post("/bundle", summary="Upload & Analyze Document Bundle")
async def upload_rfq_bundle(
    project_name: str = Form("New RFQ Project"),
    files: List[UploadFile] = File(...)
):
    """
    The 'Intelligence' Endpoint:
    1. Validates and sanitizes incoming files.
    2. Saves multiple files (PDF, XLSX, DWG) asynchronously in chunks.
    3. Runs the cross-file engineering conflict detection.
    4. Returns structured JSON including the project requirements.
    """
    saved_filepaths = []
    
    try:
        for file in files:
            # Reject empty files immediately (Note: file.size requires FastAPI >= 0.100.0)
            if file.size == 0:
                logger.warning(f"⚠️ Rejected empty file upload: {file.filename}")
                continue

            # Sanitize and create safe path
            safe_filename = sanitize_filename(file.filename or f"uploaded_{uuid4().hex}.bin")
            filepath = UPLOAD_DIR / safe_filename
            
            # Asynchronous chunked writing (prevents RAM overload on massive files)
            try:
                async with aiofiles.open(filepath, "wb") as buffer:
                    while chunk := await file.read(1024 * 1024): # 1MB chunks
                        await buffer.write(chunk)
            finally:
                # Always close the FastAPI UploadFile to free up spooled memory
                await file.close()
                
            saved_filepaths.append(str(filepath))
            logger.info(f"📁 Uploaded & Saved: {safe_filename}")

        if not saved_filepaths:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="No valid files were uploaded."
            )

        logger.info(f"🚀 Analyzing bundle for project: {project_name}")
        
        # Trigger the master orchestration pipeline
        pipeline_result = await process_rfq_bundle(
            project_name=project_name, 
            file_paths=saved_filepaths
        )

        return pipeline_result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Bundle processing failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Bundle analysis failed: {str(e)}"
        )

