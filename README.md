Here is the updated README tailored to reflect your new Agentic architecture, highlighting the specific upgrades to the RAG pipeline, vector services, LLM tool integration, and the upload router.

```md
# 🚀 RAG-AI-Agents (Agentic Upgrade)

An autonomous, multi-agent system that automates the analysis of complex **Request for Quotation (RFQ)** documents. By upgrading from a standard RAG pipeline to an **Agentic ReAct (Reason → Act → Observe)** framework, the system now autonomously selects tools, queries databases, and synthesizes cross-document engineering insights.

It eliminates manual effort by extracting insights, detecting inconsistencies, and answering queries across multiple document formats (PDF, Excel, CAD)—all in seconds.

---

## ✨ Key Features

- **🧠 Agentic Orchestration (ReAct)** The core LLM acts as an autonomous agent, evaluating user queries and dynamically calling internal tools (like hybrid search) to gather context before formulating an answer.

- **📄 Multi-Format Document Intelligence** Upgraded `upload_router` securely handles single-file processing and multi-file "Bundle" orchestrations, processing PDFs, Excel BOQs, and AutoCAD files.

- **🔍 Hybrid Smart Search (RAG as a Tool)** The upgraded `vector_service` acts as a direct tool for the agent, combining dense vector embeddings (FAISS) with lexical search to answer complex, multi-turn natural language queries.

- **⚠️ Automated Conflict Detection** Cross-references BOQs, specifications, and engineering drawings to identify critical quantity mismatches.

- **📌 Source Citations & Confidence Score** Every agentic response includes traceable references to the exact document chunk and reliability indicators.

---

## 🛠️ Setup Guide

### 1. Clone Repository
```bash
git clone <repo-link>
cd RAG-AI-Optimizer
```

### 2. Create Virtual Environment (venv)

#### 🔹 For Windows
```bash
python -m venv venv
venv\Scripts\activate
```

#### 🔹 For Mac/Linux
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Create a `.env` file in the root folder:
```env
OPENAI_API_KEY=your_openai_key
HF_TOKEN=your_huggingface_token
```

### 5. CAD File Support (Optional)
Install **ODA File Converter** and update its path in:
```
app/services/cad_service.py
```

---

## 🚀 Running the Application

```bash
uvicorn app.main:app --reload --port 8006

```

* 🌐 **Web App:** [http://127.0.0.1:8000](http://127.0.0.1:8000)
* 📘 **API Docs:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

---

## 💡 Example Queries

### 📌 Agentic Tool Execution
* "Search the uploaded documents for fire safety requirements and summarize them."

### ⚠️ Cross-Document Conflict Detection
* "Compare M-F1 vs M-F2 drawings for discrepancies."

---
To list the equipment:

/agent Use the tool to list all equipment and quantities from the BOQ_for_RFQ_Test.xlsx document.

To compare the concrete volumes:

/agent Use your tools to extract the concrete volumes from both the BOQ file and the CAD drawings, then compare them for discrepancies.

## 🧠 Updated Agentic Architecture 

```text
User Natural Language Query
   │
   ▼
[ Upload Router (/upload/search) ]
   │
   ▼
[ LLM Agent (ReAct Loop) ] ───(Analyzes Intent)
   │
   ├──▶ 🛠️ Tool Call: search_documents()
   │      ↳ [ Vector Service (FAISS + Embeddings) ]
   │
   ├──▶ 👁️ Observation: Context retrieved from DB
   │
   └──▶ 🧠 Reasoning: Synthesizes final answer
   │
   ▼
Structured Answer + Citations + Risk Insights
```

---


## ⚙️ Tech Stack

* **Backend:** FastAPI
* **Agent Engine/LLM:** OpenAI (`gpt-4o`, `text-embedding-3-large`)
* **Vector DB:** FAISS (Hybrid Search capability)
* **Frontend:** HTML, CSS, JavaScript
* **Document Parsing:** Async chunking & custom pipelines for PDF, Excel, CAD

---

## 🎯 Use Cases

* EPC & Construction RFQ Analysis
* Procurement Automation
* Engineering Document Validation
* Tender Risk Assessment

---

## 📈 Future Improvements

* Integrate LangGraph for complex multi-agent state management.
* Add fine-tuned domain-specific LLM.
* Improve CAD parsing with 3D model understanding.
* Deploy using Docker + AWS.

---

## 👩‍💻 Author

**Jaya Rajput** Full Stack Developer | AI/ML Enthusiast
```"# RAG-AI-Agent" 
