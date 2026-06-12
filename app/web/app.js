/**
 * RAG AI System - Frontend Logic (Consolidated & Optimized)
 */

document.addEventListener("DOMContentLoaded", () => {
    // --- DOM Elements ---
    const chat = document.getElementById("chat");
    const questionInput = document.getElementById("question");
    const sendBtn = document.getElementById("sendBtn");
    const dropZone = document.getElementById("dropZone");
    const fileInput = document.getElementById("fileInput");
    const fileNameDisplay = document.getElementById("fileName");
    const progressBar = document.getElementById("progress");
    const documentsContainer = document.getElementById("documents");

    // State Guards
    let isUploading = false;

    /* =========================================
       FILE MANAGEMENT (BUNDLE UPLOAD)
       ========================================= */
    if (dropZone && fileInput) {
        fileInput.style.display = "none";
        dropZone.addEventListener("click", () => {
            if (!isUploading) fileInput.click();
        });
    }

    fileInput.addEventListener("change", async () => {
        if (fileInput.files.length === 0 || isUploading) return;
        await handleFiles(fileInput.files);
        fileInput.value = ""; // Reset input so the same file can be uploaded again if needed
    });

    dropZone.addEventListener("dragover", (e) => {
        e.preventDefault();
        if (!isUploading) dropZone.classList.add("dragover");
    });

    dropZone.addEventListener("dragleave", () => {
        dropZone.classList.remove("dragover");
    });

    dropZone.addEventListener("drop", async (e) => {
        e.preventDefault();
        dropZone.classList.remove("dragover");
        if (isUploading) return;
        
        const files = e.dataTransfer.files;
        if (files.length > 0) await handleFiles(files);
    });

    async function handleFiles(files) {
        isUploading = true;
        fileNameDisplay.textContent = `Analyzing bundle of ${files.length} file(s)...`;
        progressBar.style.width = "50%";
        progressBar.style.backgroundColor = "#007bff"; 

        try {
            const responseData = await uploadBundle(files);

            fileNameDisplay.textContent = "Analysis complete!";
            progressBar.style.width = "100%";
            progressBar.style.backgroundColor = "#28a745"; // Success green

            const aiDiv = createMessageElement("ai system");
            aiDiv.innerHTML = `
                <b>📂 Documents Uploaded Successfully</b><br>
                ${[...files].map(f => "• " + f.name).join("<br>")}
            `;
            
            console.log("Extraction Data:", responseData);
            loadDocuments(); // Refresh document list

        } catch (error) {
            console.error("Bundle upload failed:", error);
            fileNameDisplay.textContent = "Upload failed.";
            progressBar.style.backgroundColor = "#dc3545"; // Error red
            alert(`Failed to process the document bundle: ${error.message}`);
        } finally {
            setTimeout(() => {
                fileNameDisplay.textContent = "";
                progressBar.style.width = "0%";
                isUploading = false;
            }, 3000);
        }
    }

    async function uploadBundle(files) {
        const formData = new FormData();
        formData.append("project_name", "Document Analysis " + new Date().toLocaleTimeString());
        
        for (let i = 0; i < files.length; i++) {
            formData.append("files", files[i]);
        }

        const response = await fetch("/api/upload/bundle", {
            method: "POST",
            body: formData
        });

        if (!response.ok) {
            const errData = await response.json().catch(() => ({}));
            throw new Error(errData.detail || response.statusText);
        }
        
        return await response.json();
    }

    /* =========================================
       CHAT FUNCTIONALITY & AGENT ROUTING
       ========================================= */

    function createMessageElement(typeClasses) {
        const div = document.createElement("div");
        div.className = `message ${typeClasses}`;
        chat.appendChild(div);
        chat.scrollTop = chat.scrollHeight;
        return div;
    }

    async function askAI() {
        const rawInput = questionInput.value.trim();
        if (!rawInput) return;

        // 1. Lock UI
        questionInput.disabled = true;
        sendBtn.disabled = true;

        // 2. Display user message
        createMessageElement("user").textContent = rawInput;
        questionInput.value = "";
        
        const aiDiv = createMessageElement("ai thinking");
        aiDiv.textContent = "Thinking...";

        try {
            // 🔥 SMART ROUTING: Detect if user wants the Agent or Standard RAG
            let endpoint = "/api/query/ask";
            let payload = { question: rawInput };
            let isAgent = false;

            if (rawInput.toLowerCase().startsWith("/agent ")) {
                endpoint = "/api/query/agent";
                payload = { query: rawInput.substring(7).trim() }; // Backend Agent schema expects 'query'
                isAgent = true;
                aiDiv.textContent = "Agent is reasoning. This may take a moment...";
            }

            const response = await fetch(endpoint, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.detail || "Server error occurred.");
            }
            
            aiDiv.classList.remove("thinking");

            // Parse Markdown safely
            let safeHtml = data.answer || "No answer provided.";
            if (typeof marked !== "undefined") {
                marked.setOptions({ breaks: true });
                let rawHtml = marked.parse(safeHtml);
                safeHtml = typeof DOMPurify !== "undefined" ? DOMPurify.sanitize(rawHtml) : rawHtml;
            }

            // Build UI Output
            let finalHtml = `<div class="markdown-body">${safeHtml}</div>`;

            // Inject sources if using standard RAG
            if (!isAgent && data.sources && data.sources.length > 0) {
                finalHtml += `
                    <div class="sources" style="margin-top:15px; font-size:0.85em; color:#666; border-top: 1px solid #eee; padding-top: 8px;">
                        <strong>Sources:</strong> ${data.sources.join(", ")}
                    </div>
                `;
            }

            aiDiv.innerHTML = finalHtml;

        } catch (error) {
            console.error("Chat Error:", error);
            aiDiv.classList.remove("thinking");
            aiDiv.classList.add("error");
            aiDiv.innerHTML = `⚠️ <b>Error:</b> ${error.message}`;
        } finally {
            // 3. Unlock UI (Crucial)
            questionInput.disabled = false;
            sendBtn.disabled = false;
            questionInput.focus();
            chat.scrollTop = chat.scrollHeight;
        }
    }

    /* =========================================
       DOCUMENT MANAGEMENT
       ========================================= */

    async function loadDocuments() {
        if (!documentsContainer) return;

        try {
            const response = await fetch("/api/documents"); 
            if (!response.ok) return;
            
            const data = await response.json();
            documentsContainer.innerHTML = "";

            if (!data.documents || data.documents.length === 0) {
                documentsContainer.innerHTML = "<p class='empty-state'>No documents uploaded yet.</p>";
                return;
            }

            data.documents.forEach(doc => {
                const div = document.createElement("div");
                div.className = "document-item";
                div.innerHTML = `<span class="doc-name">${doc}</span>`;
                
                const delBtn = document.createElement("button");
                delBtn.className = "delete-btn";
                delBtn.innerHTML = "🗑️";
                delBtn.title = "Delete Document";
                
                // Pass the button reference to disable it during deletion
                delBtn.onclick = () => deleteDocument(doc, delBtn);

                div.appendChild(delBtn);
                documentsContainer.appendChild(div);
            });
        } catch (error) {
            console.error("Error loading documents:", error);
        }
    }

    async function deleteDocument(filename, btnElement) {
        if (!confirm(`Are you sure you want to delete "${filename}"?`)) return;
        
        // Lock the button to prevent double-clicks
        btnElement.disabled = true;
        btnElement.style.opacity = "0.5";

        try {
            // 🔥 CRITICAL FIX: URI Encoding prevents crashes on filenames with spaces!
            const safeFilename = encodeURIComponent(filename);
            const response = await fetch(`/api/delete/${safeFilename}`, { method: "DELETE" });
            
            if (response.ok) {
                loadDocuments();
            } else {
                const errData = await response.json();
                alert(`Error: ${errData.detail || "Could not delete document."}`);
                btnElement.disabled = false;
                btnElement.style.opacity = "1";
            }
        } catch (error) {
            console.error("Delete Error:", error);
            alert("Error deleting document. Please check your connection.");
            btnElement.disabled = false;
            btnElement.style.opacity = "1";
        }
    }

    // Final Event Listeners
    if (sendBtn) sendBtn.onclick = askAI;
    if (questionInput) {
        questionInput.onkeydown = (e) => {
            if (e.key === "Enter" && !e.shiftKey) { // Allow shift+enter for newlines
                e.preventDefault();
                askAI();
            }
        };
    }

    // Initial Load
    loadDocuments();
});