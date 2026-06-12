import os
import logging
import fitz  # PyMuPDF

logger = logging.getLogger(__name__)

def extract_pdf(file_path: str) -> str:
    """
    Extract text from a PDF file using PyMuPDF.
    Provides superior handling of multi-column layouts and tables found in RFQs
    by sorting text blocks visually and using context managers for safe memory handling.
    """
    if not os.path.exists(file_path):
        logger.error(f"❌ PDF not found at path: {file_path}")
        return ""

    try:
        text_chunks = []
        
        # Using context manager ensures the document is properly closed automatically
        with fitz.open(file_path) as doc:
            for page_num in range(doc.page_count):
                page = doc.load_page(page_num)
                # sort=True forces reading order (left-to-right, top-to-bottom)
                # This is crucial for multi-column RFQ documents and basic tables
                page_text = page.get_text("text", sort=True)
                
                page_text_str = str(page_text)
                if page_text_str.strip():
                    # Clean up excessive newlines for cleaner LLM context and reduced token count
                    cleaned_text = "\n".join(line for line in page_text_str.splitlines() if line.strip())
                    
                    # Add a page marker so the Agent/LLM knows where it is in the document
                    text_chunks.append(f"--- PAGE {page_num + 1} ---\n{cleaned_text}")

        logger.info(f"✅ Successfully extracted {len(text_chunks)} pages from PDF.")
        return "\n\n".join(text_chunks).strip()

    except Exception as e:
        logger.error(f"❌ Critical failure extracting PDF {file_path}. Error: {e}", exc_info=True)
        raise ValueError(f"Failed to read PDF file: {e}")