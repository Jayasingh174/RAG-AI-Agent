import json
import logging
import asyncio
from aiofiles import os as aio_os
import pandas as pd
from openai import AsyncOpenAI
from typing import Any, cast
from pathlib import PurePath

from app.config import (
    OPENAI_API_KEY,
    OPENAI_MODEL,
    OPENAI_TEMPERATURE,
    OPENAI_MAX_TOKENS,
    UPLOAD_DIR,
)


logger = logging.getLogger(__name__)
client = AsyncOpenAI(api_key=OPENAI_API_KEY)

# ==========================================
# 🧠 STANDARD RAG Q&A
# ==========================================
async def ask_llm(question: str, context: str = "", mode: str = "qa"):
    """
    Standardizes the LLM call. Adding 'mode' prevents the 
    unexpected keyword argument error.
    """
    logger.info(f"Processing query. Context length: {len(context) if context else 0}")
    
    if not context or len(context.strip()) < 10:
        logger.warning("Empty context provided to LLM.")
        return "No relevant data found in uploaded documents. Please ensure your files contain readable text."

    try:
        safe_context = context[:100000] 

        system_prompt = (
            "You are an intelligent Document Analysis Assistant powered by RAG.\n"
            "Answer the user's question strictly using the provided context. "
            "If the exact information is missing from the context, state exactly: 'Information not available in the documents.' Do not guess.\n\n"
            "*** CRITICAL FORMATTING RULES ***\n"
            "1. FOR TABLES: If summarizing data, comparing documents, or listing items, use standard Markdown tables. DO NOT wrap Markdown tables inside code blocks or triple backticks.\n"
            "2. FOR CSV/CODE: If the user explicitly asks for a CSV file, raw code, or raw data, you MUST wrap the dataset inside a markdown code block using triple backticks (e.g., ```csv )."
        )

        response = await client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Context:\n{safe_context}\n\nQuestion: {question}"}
            ],
            temperature=OPENAI_TEMPERATURE,
            max_tokens=OPENAI_MAX_TOKENS,
        )

        answer = response.choices[0].message.content

        if not answer or not answer.strip():
            return "Information not available in the documents."

        return answer.strip()

    except Exception as e:
        logger.error(f"LLM Integration Error: {str(e)}", exc_info=True)
        return "LLM processing failed. Please check API connectivity or model availability."

# ==========================================
# 🛠️ LOCAL AGENT TOOLS
# ==========================================
async def calculate_totals(items: list) -> str:
    """Tool: Calculates the sum of item quantities."""
    logger.info(f"🛠️ Tool Executed: calculate_totals | Items: {len(items)}")
    try:
        df = pd.DataFrame(items)
        if 'quantity' not in df.columns:
            return "Error: Could not find 'quantity' data to calculate."
        df['quantity'] = pd.to_numeric(df['quantity'], errors='coerce').fillna(0)
        total = df['quantity'].sum()
        return f"The calculated total quantity for the provided items is: {total}"
    except Exception as e:
        logger.error(f"❌ Calculate tool failed: {e}")
        return f"Error calculating totals: {str(e)}"

async def extract_table(document_name: str) -> str:
    """Extracts tabular data directly from Excel files or vector store."""
    logger.info(f"🛠️ Tool Executed: extract_table | Requested Target: {document_name}")

    target_file = None
    clean_search_name = document_name.lower().replace(".xlsx", "").replace(".csv", "").replace(".pdf", "").strip()

    try:
        exists_result = aio_os.path.exists(UPLOAD_DIR)
        exists = await exists_result if asyncio.iscoroutine(exists_result) else exists_result

        if exists:
            list_result = aio_os.listdir(UPLOAD_DIR)
            files = await list_result if asyncio.iscoroutine(list_result) else list_result

            for f in files:
                if clean_search_name in f.lower():
                    target_file = f
                    break
    except Exception as e:
        logger.error(f"❌ Error accessing upload directory: {e}")
        return f"Error accessing upload directory: {str(e)}"

    if target_file:
        if target_file.lower().endswith(('.xlsx', '.xls', '.csv')):
            logger.info(f"📂 Found tabular file: {target_file}. Reading with Pandas...")
            file_path = str(PurePath(UPLOAD_DIR) / target_file)
            try:
                df = pd.read_csv(file_path) if target_file.lower().endswith('.csv') else pd.read_excel(file_path)
                csv_data = df.to_csv(index=False)
                return f"Raw Data from {target_file}:\n```csv\n{csv_data}\n```"
            except Exception as e:
                logger.error(f"❌ Failed to read {target_file} with Pandas: {e}")
                return f"Error reading {target_file}: {str(e)}"
        else:
            logger.info(f"Found file '{target_file}' but it is not a tabular file.")
            return f"Found file '{target_file}', but it is not a tabular (.csv/.xlsx/.xls) file. Please provide a tabular file."

    logger.info(f"No matching uploaded file found for: {document_name}")
    return "No matching uploaded file found. Please upload the document or specify a different filename."

# ==========================================
# 🤖 MULTI-STEP AGENT REASONING LOOP
# ==========================================
async def run_agent_loop(user_command: str):
    """
    Executes the Agent reasoning loop: 
    User Query -> Agent -> Tool Selection -> Execution -> LLM Reasoning
    """
    tools = [
        {
            "type": "function",
            "function": {
                "name": "search_documents",
                "description": "Searches the RFQ document for specific information like scope, materials, or risks.",
                "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}
            }
        },
        {
            "type": "function",
            "function": {
                "name": "calculate_totals",
                "description": "Calculates the sum total of a list of item quantities.",
                "parameters": {"type": "object", "properties": {"items": {"type": "array", "items": {"type": "object"}}}, "required": ["items"]}
            }
        },
        {
            "type": "function",
            "function": {
                "name": "extract_table",
                "description": "Extracts tabular BOQ or BOM data from a specified document.",
                "parameters": {"type": "object", "properties": {"document_name": {"type": "string", "description": "The EXACT filename"}}, "required": ["document_name"]}
            }
        }
    ]

    try:
        exists_result = aio_os.path.exists(UPLOAD_DIR)
        exists = await exists_result if asyncio.iscoroutine(exists_result) else exists_result

        if exists:
            list_result = aio_os.listdir(UPLOAD_DIR)
            files = await list_result if asyncio.iscoroutine(list_result) else list_result
            available_files = [str(f) for f in files] if files else []
        else:
            available_files = []

        file_list_str = ", ".join(available_files) if available_files else "No files found."
    except Exception:
        file_list_str = "Unknown"

    messages = [
        {"role": "system", "content": (
            "You are an analytical Engineering Assistant. "
            f"Here are the exact files currently available in the system: [{file_list_str}].\n"
            "CRITICAL RULES:\n"
            "1. When the user asks about a generic file (e.g., 'the BOQ' or 'the CAD drawings'), look at the available files list and use the EXACT filename when calling tools.\n"
            "2. Use 'extract_table' for Excel (.xlsx) files.\n"
            "3. Use 'search_documents' for PDFs and DWG/DXF files to find specific volumes, text, or specifications.\n"
            "4. Answer the user's specific question directly. Compare the data if asked.\n"
            "5. If the user asks for specific data (like concrete volume) and it does not exist, briefly explain WHAT the document actually is based on the items you found (e.g., 'This appears to be a Fire Suppression BOQ, so it does not contain structural concrete data')"
        )},
        {"role": "user", "content": user_command}
    ]

    logger.info(f"Starting Agent Loop. Files visible to agent: {file_list_str}")

    while True:
        response = await client.chat.completions.create(
            model=OPENAI_MODEL, messages=cast(Any, messages), tools=cast(Any, tools), tool_choice="auto"
        )
        msg = response.choices[0].message
        
        assistant_msg = msg.model_dump(exclude_unset=True)
        if assistant_msg.get("content") is None:
            assistant_msg["content"] = ""
            
        messages.append(assistant_msg)

        if not msg.tool_calls:
            return msg.content

        for tool_call in msg.tool_calls:
            function_obj = getattr(tool_call, "function", None)
            if function_obj is not None:
                name = getattr(function_obj, "name", None) or getattr(tool_call, "name", None)
                args_raw = getattr(function_obj, "arguments", "{}")
                tool_id = getattr(tool_call, "id", "") or ""
            else:
                name = getattr(tool_call, "name", None) or ""
                args_raw = getattr(tool_call, "arguments", "{}")
                tool_id = getattr(tool_call, "id", "") or ""

            try:
                if isinstance(args_raw, str):
                    args = json.loads(args_raw) if args_raw else {}
                else:
                    args = args_raw
            except json.JSONDecodeError:
                args = {}

            logger.info(f"Agent executing tool: {name} with args: {args}")

            from app.pipeline.query_pipeline import search_documents

            if name == "search_documents":
                result = await search_documents(args.get('query', ''))
            elif name == "calculate_totals":
                result = await calculate_totals(args.get('items', []))
            elif name == "extract_table":
                result = await extract_table(args.get('document_name', ''))
            else:
                result = "Tool not found."

            messages.append({
                "tool_call_id": str(tool_id),
                "role": "tool",
                "name": str(name or ""),
                "content": str(result)
            })