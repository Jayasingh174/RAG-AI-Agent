import os
import logging
from typing import List, Dict, Any

# Extraction services
from app.services.pdf_service import extract_pdf
from app.services.docx_service import extract_docx
from app.services.csv_service import extract_csv
from app.services.excel_service import extract_boq_data
from app.services.text_service import extract_text
from app.services.cad_service import extract_dwg, summarize_dxf

# AI pipeline services
from app.brain.chunk_service import chunk_text
from app.brain.embedding_service import embed_texts

# Import the unified VectorService instance
from app.brain.vector_service import vector_store 

from app.config import DWG_TEMP_DIR

logger = logging.getLogger(__name__)

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

SUPPORTED_EXTENSIONS = {
    ".pdf", ".docx", ".csv", ".xlsx", ".xls", ".txt", ".dwg", ".dxf"
}

# ==========================================
# 🛠️ HELPER: FUZZY DICTIONARY MATCHER
# ==========================================
def normalize_row(row_dict: Any) -> Dict[str, Any]:
    """Safely converts row keys to lowercase strings for efficient matching."""
    if not isinstance(row_dict, dict):
        return {}
    return {str(k).lower().strip(): v for k, v in row_dict.items() if k}

def get_fuzzy_val(normalized_row: Dict[str, Any], possible_keys: List[str]) -> str:
    """Checks a pre-normalized dictionary for multiple possible column names."""
    for key in possible_keys:
        clean_key = key.lower()
        if clean_key in normalized_row and normalized_row[clean_key] is not None:
            return str(normalized_row[clean_key]).strip()
    return ""

# ==========================================
# 📄 MAIN INGESTION ORCHESTRATOR
# ==========================================
async def process_document(file_path: str) -> str:
    """
    Validates, extracts text/BOQ/CAD data, chunks, embeds, and stores in Vector DB.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    if os.path.getsize(file_path) > MAX_FILE_SIZE:
        raise ValueError(f"File exceeds maximum allowed size ({MAX_FILE_SIZE // (1024*1024)}MB)")

    ext = os.path.splitext(file_path)[1].lower()

    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported file type: {ext}")

    try:
        chunks: List[str] = []
        clean_text = ""

        # 1️⃣ EXCEL (BOQ Handling)
        if ext in [".xlsx", ".xls"]:
            boq_data = extract_boq_data(file_path)

            if not boq_data:
                raise ValueError("No data extracted from Excel")

            for row in boq_data:
                lower_row = normalize_row(row)
                if not lower_row:
                    continue

                item = get_fuzzy_val(lower_row, ["item", "item no", "s.no", "id", "no."])
                desc = get_fuzzy_val(lower_row, ["material", "description", "item description", "name", "spec"])
                qty = get_fuzzy_val(lower_row, ["quantity", "qty", "qty.", "amount"])
                unit = get_fuzzy_val(lower_row, ["unit", "uom", "unit of measure"])

                if not desc and not qty:
                    continue

                text_chunk = f"Item {item}: {desc} | Qty: {qty} {unit}"
                chunks.append(text_chunk)

            clean_text = "\n".join(chunks)
            logger.info(f"📊 Excel processed → {len(chunks)} BOQ chunks")

        # 2️⃣ OTHER FILE TYPES (Including CAD)
        else:
            if ext == ".pdf":
                raw = extract_pdf(file_path)
            elif ext == ".docx":
                raw = extract_docx(file_path)
            elif ext == ".csv":
                raw = extract_csv(file_path)
            elif ext == ".txt":
                raw = extract_text(file_path)
            elif ext == ".dwg":
                raw = extract_dwg(file_path, DWG_TEMP_DIR)
            elif ext == ".dxf":
                raw = summarize_dxf({"file_path": file_path})
            else:
                raw = ""

            # Handle outputs that return dicts with metadata vs raw strings
            if isinstance(raw, dict):
                text_chunks = raw.get("text_chunks", [])
                summary = raw.get("summary", "")
                clean_text = f"{summary}\n\n{' '.join(text_chunks)}"
            else:
                clean_text = str(raw)

            clean_text = clean_text.strip()

            if len(clean_text) < 10:
                raise ValueError("No meaningful text extracted")

            raw_chunks = chunk_text(clean_text)
            chunks = [c.strip() for c in raw_chunks if c and len(c.strip()) > 20]

            logger.info(f"📄 Text/CAD processed → {len(chunks)} chunks")

        if not chunks:
            raise ValueError("No valid chunks generated")

        # 3️⃣ EMBEDDINGS & STORAGE
        embeddings = await embed_texts(chunks)

        if embeddings is None or len(embeddings) == 0:
            raise ValueError("Embedding generation failed")

        filename = os.path.basename(file_path)

        vector_store.add_documents(
            chunks=chunks,
            embeddings=embeddings,
            source_filename=filename
        )

        logger.info(f"✅ Document indexed successfully: {filename}")
        return clean_text

    except Exception as e:
        logger.error(f"❌ Document processing failed: {file_path} | {e}", exc_info=True)
        raise RuntimeError(f"Document processing failed: {e}") from e