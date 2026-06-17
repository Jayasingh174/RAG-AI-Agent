import os
import re
import json
import logging
import asyncio
import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

from openai import AsyncOpenAI
from pydantic import BaseModel, Field, ValidationError

# --- Internal Services ---
from app.config import UPLOAD_DIR, OPENAI_API_KEY
from app.brain.document_service import process_document
from app.brain.vector_service import vector_store
from app.brain.conflict_engine import detect_conflicts
from app.services.cad_service import extract_dwg
from app.services.excel_service import extract_boq_data
from app.pipeline.intelligence_service import DocumentIntelligence

# --- Orchestration Tools ---
from app.brain.llm_service import ask_llm
from app.pipeline.optimization_service import retrieve_and_rerank, compress_context

logger = logging.getLogger(__name__)

# ==========================================================
# 🛡️ PYDANTIC SCHEMAS
# ==========================================================

class BOMItem(BaseModel):
    name: str = Field(..., description="Normalized item name")
    qty: int = Field(..., gt=0, description="Must be positive")
    unit: str = Field(default="Nos", description="Unit of measurement")

class ExtractionSchema(BaseModel):
    project: str = Field(default="Unknown Project")
    items: List[BOMItem] = Field(default_factory=list)

# ==========================================================
# 🧹 UTILITY HELPERS
# ==========================================================

def safe_int(val, default=1) -> int:
    """Converts mixed strings (e.g., '25 Nos') into clean integers."""
    try:
        num_str = re.sub(r"[^\d.]", "", str(val))
        return int(float(num_str)) if num_str else default
    except Exception:
        return default

def clean_item(text: str) -> str:
    """Normalizes item names for cross-file matching."""
    text = str(text).lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()

def standardize_unit(unit_str: str) -> str:
    """Standardizes units (e.g., 'Nos' -> 'ea')."""
    mapping = {"nos": "ea", "numbers": "ea", "each": "ea", "m": "meter", "mtr": "meter", "mm": "millimeter"}
    return mapping.get(str(unit_str).lower().strip(), unit_str.lower().strip())

def normalize_entity(item, quantity, source, etype, path, unit="Nos") -> Dict:
    """Standardizes data structure for conflict detection."""
    return {
        "item": clean_item(item),
        "quantity": safe_int(quantity),
        "unit": standardize_unit(unit),
        "source": source,
        "type": etype,
        "file_path": path,
    }

def deduplicate_entities(entities: List[Dict]) -> List[Dict]:
    """Ensures unique entries to prevent double-counting."""
    seen = set()
    unique = []
    for e in entities:
        key = (e.get("item"), e.get("type"), e.get("file_path"))
        if key not in seen:
            seen.add(key)
            unique.append(e)
    return unique

# ==========================================================
# 📄 CORE: SINGLE FILE PIPELINE
# ==========================================================

async def process_rfq(file_path: str) -> Dict[str, Any]:
    """Ingests, parses, extracts, and analyzes a single document."""
    filename = os.path.basename(file_path)
    try:
        logger.info(f"🚀 Processing: {filename}")
        await process_document(file_path)  

        # Retrieve text from vector store for this specific file
        file_chunks = [c["text"] for c in vector_store.documents if c.get("metadata", {}).get("source") == filename]
        clean_text = "\n\n".join(file_chunks)

        if len(clean_text.strip()) < 10:
            raise ValueError(f"No meaningful text found in {filename}.")

        # LLM Data Extraction
        intelligence = DocumentIntelligence()
        raw_data = await intelligence.extract_structured_data(clean_text)
        
        # Validation
        try:
            validated = ExtractionSchema(**raw_data)
        except ValidationError:
            validated = ExtractionSchema(project="Validation Fallback", items=[])

        # Conflict Detection
        extracted_items = [item.dict() for item in validated.items]
        mapped = [{"item": i["name"], "quantity": i["qty"], "source": filename} for i in extracted_items]
        
        result = {
            "status": "success", 
            "source_file": filename, 
            "project": validated.project,
            "items": extracted_items, 
            "conflicts": detect_conflicts(mapped)
        }

        # Handle CAD specific metadata
        if file_path.lower().endswith((".dwg", ".dxf")):
            result["cad_summary"] = extract_dwg(file_path, output_dir=UPLOAD_DIR).get("summary")

        return result

    except Exception as e:
        logger.error(f"❌ Pipeline error in {filename}: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}

# ==========================================================
# 🚀 ORCHESTRATION: BUNDLE PROCESSING
# ==========================================================

async def process_file_task(path: Path, index: int, total: int, semaphore: asyncio.Semaphore) -> Dict[str, Any]:
    """Task worker for concurrent processing with semaphore limit."""
    async with semaphore:
        filename = path.name
        try:
            result = await process_rfq(str(path))
            if result.get("status") == "error":
                raise ValueError(result.get("message"))

            # Save raw requirements
            with open(f"deliverables/req_{filename}.json", "w") as f:
                json.dump(result, f, indent=4)

            # Extract entities for cross-file comparison
            entities = []
            if path.suffix.lower() in {".xlsx", ".xls"}:
                for row in extract_boq_data(str(path)):
                    entities.append(normalize_entity(row.get("Item"), row.get("Quantity"), f"BOQ ({filename})", "BOQ", str(path)))
            else:
                for item in result.get("items", []):
                    entities.append(normalize_entity(item.get("name"), item.get("qty"), f"BOM ({filename})", "BOM", str(path), item.get("unit")))
            
            return {"success": True, "file": filename, "entities": entities}

        except Exception as e:
            return {"success": False, "file": filename, "message": str(e), "entities": []}

async def process_rfq_bundle(project_name: str, file_paths: List[str]) -> Dict[str, Any]:
    """Orchestrates concurrent processing and generates final report."""
    semaphore = asyncio.Semaphore(5) # Rate limit to 5 concurrent tasks
    paths = [Path(p) for p in file_paths]
    
    tasks = [process_file_task(p, i, len(paths), semaphore) for i, p in enumerate(paths)]
    results = await asyncio.gather(*tasks)

    # Aggregate & Analyze
    all_entities = deduplicate_entities([e for r in results for e in r.get("entities", [])])
    conflict_report = detect_conflicts(all_entities) if all_entities else {"message": "No data for analysis."}
    
    # Save Report
    final_output = {
        "project_name": project_name,
        "timestamp": datetime.datetime.now().isoformat(),
        "engineering_analysis": conflict_report
    }
    
    safe_project = re.sub(r'[\\/*?:"<>|]', "_", project_name)
    report_path = f"deliverables/{safe_project}_Report.json"
    
    with open(report_path, "w") as f:
        json.dump(final_output, f, indent=4)
    logger.info(f"✅ Bundle processing complete. Report saved to {report_path}")
    return final_output

# ==========================================================
# 🧪 DEBUG UTILITIES
# ==========================================================
if __name__ == "__main__":
    # Test harness
    print(f"Total chunks in vector store: {len(vector_store.documents)}")
