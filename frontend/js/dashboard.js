import { uploadPdf, generateVideo, getHistory, saveApiKeys, getApiKeys } from "./api.js";

if (window.__dashboard_booted) {
    console.warn("[DASHBOARD] Prevented duplicate initialization");
} else {
    window.__dashboard_booted = true;

    // Global controllers for request cancellation
    window.__upload_abort_controller = null;
    window.__generate_abort_controller = null;
    window.__history_abort_controller = null;

    // Track active operation state for beforeunload locks
    let isUploading = false;
    let isGenerating = false;

    // Safe helper to abort active operations
    window.abortActiveOperations = () => {
        console.log("[DASHBOARD] Aborting all active network operations...");
        if (window.__upload_abort_controller) {
            window.__upload_abort_controller.abort();
            window.__upload_abort_controller = null;
        }
        if (window.__generate_abort_controller) {
            window.__generate_abort_controller.abort();
            window.__generate_abort_controller = null;
        }
        if (window.__history_abort_controller) {
            window.__history_abort_controller.abort();
            window.__history_abort_controller = null;
        }
        isUploading = false;
        isGenerating = false;
    };

    // Register beforeunload event listener to alert user if leaving during active operations
    window.addEventListener("beforeunload", (e) => {
        if (isUploading || isGenerating) {
            e.preventDefault();
            const warningMessage = "An active file upload or video compilation is currently in progress. Leaving this page will cancel the operation.";
            e.returnValue = warningMessage;
            return warningMessage;
        }
    });

    // Mapped DOM Elements
    let dropzone, fileInput, fileSelectedInfo, filenameLabel, pagesCountLabel;
    let voiceSelect, speedSlider, speedValueLabel;
    let generateBtn, pipelineProgress, progressFill, progressStatusText;
    let videoHistoryGrid, emptyHistoryPlaceholder;
    let settingsModal, settingsNavBtn, settingsOverlay, closeSettingsBtn, cancelSettingsBtn, saveSettingsBtn;
    let geminiInput, deepgramInput;

    let uploadedStoragePath = "";
    let selectedFile = null;

    // Render helper for historical video cards
    function renderVideoCard(item, prepend = false) {
        const videoUrl = item.video_url || item.url || item.public_url || "";
        if (!videoUrl) {
            console.warn("missing video_url warnings:", item);
            return;
        }

        const card = document.createElement("div");
        card.className = "video-card glass";
        
        const titleText = item.title || item.name || "Untitled Video";
        const createdDate = item.created_at ? new Date(item.created_at).toLocaleDateString() : "Recent";
        
        card.innerHTML = `
            <div class="video-preview-container">
                <video src="${videoUrl}" controls preload="metadata" class="preview-player"></video>
            </div>
            <div class="video-meta">
                <h4 class="meta-title" title="${titleText}">${titleText}</h4>
                <div class="meta-sub">
                    <span>Status: <strong class="badge-success">Success</strong></span>
                    <span>Created: ${createdDate}</span>
                </div>
            </div>
            <div class="video-card-actions">
                <a href="${videoUrl}" download="${item.name || 'video.mp4'}" target="_blank" class="btn-card-action btn-download-action">
                    <span>📥</span> Download MP4
                </a>
            </div>
        `;
        
        console.log("each rendered card:", card);

        if (prepend) {
            if (emptyHistoryPlaceholder) {
                emptyHistoryPlaceholder.classList.add("hidden");
            }
            videoHistoryGrid.insertBefore(card, videoHistoryGrid.firstChild);
        } else {
            videoHistoryGrid.appendChild(card);
        }
        console.log("DOM append success:", card);
    }

    function prependVideoCard(videoData) {
        renderVideoCard(videoData, true);
    }

    // Fetch Public Archives History (Isolated, lock-guarded)
    async function loadHistory(userId) {
        if (window.__history_loading) {
            console.warn("[DASHBOARD] History fetch already in progress. Bypassing duplicate call.");
            return;
        }
        
        window.__history_loading = true;
        console.log("[HISTORY] Loading history");

        if (window.__history_abort_controller) {
            window.__history_abort_controller.abort();
        }
        window.__history_abort_controller = new AbortController();

        try {
            const response = await getHistory(userId, window.__history_abort_controller.signal);
            console.log("raw history response:", response);
            
            if (!videoHistoryGrid) {
                console.error("[FATAL] Video history grid element #video-history-grid was not found in DOM.");
                return;
            }
            
            let videos = [];
            if (response) {
                if (Array.isArray(response)) {
                    videos = response;
                } else if (response.videos && Array.isArray(response.videos)) {
                    videos = response.videos;
                } else if (response.data && Array.isArray(response.data)) {
                    videos = response.data;
                }
            }
            
            if (!Array.isArray(videos)) {
                console.error("[DASHBOARD] Normalized videos is not an array:", videos);
                videos = [];
            }
            
            console.log("normalized videos array:", videos);
            
            // Sort videos newest first
            videos.sort((a, b) => new Date(b.created_at || 0) - new Date(a.created_at || 0));

            // Clear only video cards, keeping emptyHistoryPlaceholder in the DOM
            const cards = videoHistoryGrid.querySelectorAll(".video-card");
            cards.forEach(card => card.remove());

            if (videos.length === 0) {
                if (emptyHistoryPlaceholder) {
                    emptyHistoryPlaceholder.classList.remove("hidden");
                }
                return;
            }

            if (emptyHistoryPlaceholder) {
                emptyHistoryPlaceholder.classList.add("hidden");
            }

            videos.forEach(item => {
                renderVideoCard(item);
            });
            console.log("[DASHBOARD] History refreshed");
            console.log("[HISTORY] Total rendered cards:", videos.length);
        } catch (error) {
            if (error.name !== "AbortError") {
                console.error("[DASHBOARD] History loader error:", error);
            }
        } finally {
            window.__history_loading = false;
        }
    }

    function setupHistoryPolling(userId, intervalMs = 60000) {
        if (window.__history_interval) {
            clearInterval(window.__history_interval);
        }
        
        console.log(`[DASHBOARD] Initializing singleton history polling interval (${intervalMs}ms)...`);
        window.__history_interval = setInterval(() => {
            loadHistory(userId);
        }, intervalMs);
    }

    async function handleFileSelection(file, userId) {
        if (!file.name.toLowerCase().endsWith(".pdf")) {
            alert("Only PDF files are supported.");
            return;
        }
        if (isUploading) {
            alert("An upload is already in progress.");
            return;
        }
        
        selectedFile = file;
        isUploading = true;
        console.log("[DASHBOARD] Upload started");

        if (fileSelectedInfo) {
            fileSelectedInfo.classList.remove("hidden");
        }
        if (filenameLabel) {
            filenameLabel.textContent = file.name;
        }
        if (pagesCountLabel) {
            pagesCountLabel.textContent = "Uploading & parsing PDF metadata...";
        }
        if (generateBtn) {
            generateBtn.disabled = true;
        }

        if (window.__upload_abort_controller) {
            window.__upload_abort_controller.abort();
        }
        window.__upload_abort_controller = new AbortController();

        try {
            const result = await uploadPdf(file, userId, window.__upload_abort_controller.signal);
            console.log("[DASHBOARD] Upload success:", result);
            uploadedStoragePath = result.storage_path;
            
            if (pagesCountLabel) {
                pagesCountLabel.textContent = `Document parsed successfully! Pages Count: ${result.pages_count}`;
            }
            if (generateBtn) {
                generateBtn.disabled = false;
            }
        } catch (error) {
            if (error.name === "AbortError") {
                console.warn("[DASHBOARD] PDF upload aborted.");
                return;
            }
            alert(`File processing failed: ${error.message}`);
            if (pagesCountLabel) {
                pagesCountLabel.textContent = "Upload failed. Please try again.";
            }
        } finally {
            isUploading = false;
        }
    }

    function updateProgressText(text) {
        if (progressStatusText) progressStatusText.textContent = text;
    }

    function showToast(message, type = "success") {
        const container = document.getElementById("toast-container");
        if (!container) return;
        
        const toast = document.createElement("div");
        toast.className = `toast ${type}`;
        
        const icon = type === "success" ? "✅" : "❌";
        toast.innerHTML = `<span>${icon}</span> <span>${message}</span>`;
        
        container.appendChild(toast);
        
        setTimeout(() => {
            toast.style.animation = "toast-in 0.3s reverse forwards ease";
            setTimeout(() => {
                toast.remove();
            }, 300);
        }, 4000);
    }

    async function openSettings() {
        if (settingsModal) {
            settingsModal.classList.remove("hidden");
            if (geminiInput) geminiInput.placeholder = "Loading key state...";
            if (deepgramInput) deepgramInput.placeholder = "Loading key state...";
            try {
                const keys = await getApiKeys();
                if (geminiInput) {
                    geminiInput.value = keys.gemini_key || "";
                    geminiInput.placeholder = "Enter Gemini API Key";
                }
                if (deepgramInput) {
                    deepgramInput.value = keys.deepgram_key || "";
                    deepgramInput.placeholder = "Enter Deepgram API Key";
                }
            } catch (err) {
                showToast("Failed to fetch current API keys.", "error");
                if (geminiInput) geminiInput.placeholder = "Enter Gemini API Key";
                if (deepgramInput) deepgramInput.placeholder = "Enter Deepgram API Key";
            }
        }
    }

    function closeSettings() {
        if (settingsModal) {
            settingsModal.classList.add("hidden");
        }
    }

    async function loadInitialKeys() {
        console.log("[SETTINGS] Loading API keys");
        try {
            const keys = await getApiKeys();
            if (geminiInput) geminiInput.value = keys.gemini_key || "";
            if (deepgramInput) deepgramInput.value = keys.deepgram_key || "";
        } catch (err) {
            console.warn("[DASHBOARD] Silent initial keys fetch failed:", err);
        }
    }

    async function initializeDashboard() {
        console.log("[BOOT] Dashboard initialized once");

        // Session Restoration & Guards
        const token = localStorage.getItem("supabase_access_token");
        const userJson = localStorage.getItem("supabase_user");
        const expiresAt = localStorage.getItem("supabase_expires_at");
        
        let isValid = true;
        if (!token || !userJson) {
            isValid = false;
        } else if (expiresAt) {
            const expiresTime = parseInt(expiresAt, 10);
            if (Date.now() > expiresTime) {
                console.warn("[DASHBOARD] Access denied. Session has expired.");
                isValid = false;
            }
        }
        
        if (!isValid) {
            console.warn("[DASHBOARD] Access denied. Session tokens absent or expired.");
            localStorage.removeItem("supabase_access_token");
            localStorage.removeItem("supabase_refresh_token");
            localStorage.removeItem("supabase_expires_at");
            localStorage.removeItem("supabase_user");
            window.location.href = "index.html";
            return;
        }
        
        const user = JSON.parse(userJson);
        const userEmailElement = document.getElementById("user-email");
        if (userEmailElement) {
            userEmailElement.textContent = user.email || "active_user@narrate.it";
        }

        // Elements Mapping
        dropzone = document.getElementById("dropzone");
        fileInput = document.getElementById("file-input");
        fileSelectedInfo = document.getElementById("file-selected-info");
        filenameLabel = document.getElementById("filename-label");
        pagesCountLabel = document.getElementById("pages-count-label");
        
        voiceSelect = document.getElementById("voice-select");
        speedSlider = document.getElementById("speed-slider");
        speedValueLabel = document.getElementById("speed-value");
        
        generateBtn = document.getElementById("generate-btn");
        pipelineProgress = document.getElementById("pipeline-progress");
        progressFill = document.getElementById("progress-fill");
        progressStatusText = document.getElementById("progress-status-text");
        
        videoHistoryGrid = document.querySelector("#video-history-grid");
        if (!videoHistoryGrid) {
            console.error("[FATAL] Video history grid element #video-history-grid was not found in DOM.");
        }
        emptyHistoryPlaceholder = document.getElementById("empty-history-placeholder");

        settingsModal = document.getElementById("settings-modal");
        settingsNavBtn = document.getElementById("settings-nav-btn");
        settingsOverlay = document.getElementById("settings-overlay");
        closeSettingsBtn = document.getElementById("close-settings-btn");
        cancelSettingsBtn = document.getElementById("cancel-settings-btn");
        saveSettingsBtn = document.getElementById("save-settings-btn");
        
        geminiInput = document.getElementById("gemini-key-input");
        deepgramInput = document.getElementById("deepgram-key-input");

        // Event Bindings
        if (speedSlider && speedValueLabel) {
            speedSlider.addEventListener("input", (e) => {
                const val = parseFloat(e.target.value).toFixed(2);
                let speedText = "Normal";
                if (val < 1.0) speedText = "Slow";
                if (val > 1.0) speedText = "Fast";
                speedValueLabel.textContent = `${val}x (${speedText})`;
            });
        }

        if (dropzone && fileInput) {
            dropzone.addEventListener("click", () => fileInput.click());
            
            dropzone.addEventListener("dragover", (e) => {
                e.preventDefault();
                dropzone.classList.add("dragover");
            });
            
            dropzone.addEventListener("dragleave", () => {
                dropzone.classList.remove("dragover");
            });
            
            dropzone.addEventListener("drop", (e) => {
                e.preventDefault();
                dropzone.classList.remove("dragover");
                const files = e.dataTransfer.files;
                if (files.length > 0) {
                    handleFileSelection(files[0], user.id);
                }
            });
            
            fileInput.addEventListener("change", (e) => {
                if (e.target.files.length > 0) {
                    handleFileSelection(e.target.files[0], user.id);
                }
            });
        }

        if (generateBtn) {
            generateBtn.addEventListener("click", async () => {
                if (!uploadedStoragePath) {
                    alert("Please upload a PDF file first.");
                    return;
                }
                if (isGenerating) {
                    alert("Video compilation is already in progress.");
                    return;
                }

                isGenerating = true;
                console.log("[DASHBOARD] Generation started");

                // Lock UI controls
                generateBtn.disabled = true;
                if (dropzone) dropzone.style.pointerEvents = "none";
                if (voiceSelect) voiceSelect.disabled = true;
                if (speedSlider) speedSlider.disabled = true;

                if (pipelineProgress) {
                    pipelineProgress.classList.remove("hidden");
                }

                const progressFillEl = document.getElementById("progress-fill");
                if (progressFillEl) {
                    progressFillEl.classList.remove("indeterminate");
                    progressFillEl.style.width = "0%";
                }

                updateProgressText("Phase 1: Uploading PDF (10%)");
                if (progressFillEl) {
                    progressFillEl.style.width = "10%";
                }

                const voiceName = voiceSelect ? voiceSelect.value : "aura-asteria-en";
                const speedVal = speedSlider ? parseFloat(speedSlider.value) : 1.0;
                let pace = "normal";
                if (speedVal < 1.0) pace = "slow";
                if (speedVal > 1.0) pace = "fast";

                const payload = {
                    pdf_path: uploadedStoragePath,
                    voice_name: voiceName,
                    pace: pace,
                    user_id: user.id
                };

                if (window.__generate_abort_controller) {
                    window.__generate_abort_controller.abort();
                }
                window.__generate_abort_controller = new AbortController();

                try {
                    const response = await generateVideo(
                        payload,
                        (phase, progress, message) => {
                            if (progressFillEl) {
                                progressFillEl.style.width = `${progress}%`;
                            }
                            updateProgressText(`${message} (${progress}%)`);
                        },
                        window.__generate_abort_controller.signal
                    );

                    if (progressFillEl) {
                        progressFillEl.style.width = "100%";
                    }
                    updateProgressText("Complete! Saving to video history...");
                    console.log("[DASHBOARD] Generation completed successfully:", response);

                    // Prepend newly generated video card to the history layout immediately after stream complete
                    if (response && (response.video_url || response.url)) {
                        const newVideo = {
                            name: response.file_name || "narrate_it_output.mp4",
                            url: response.video_url || response.url,
                            video_url: response.video_url || response.url,
                            created_at: new Date().toISOString()
                        };
                        prependVideoCard(newVideo);
                    }

                    // Force history reload to keep all client elements synchronized
                    await loadHistory(user.id);

                    alert("Video generated successfully!");
                } catch (error) {
                    if (progressFillEl) {
                        progressFillEl.style.width = "0%";
                    }

                    if (error.name === "AbortError") {
                        console.warn("[DASHBOARD] Generation aborted.");
                        updateProgressText("Generation aborted.");
                        return;
                    }

                    alert(`Video compilation failed: ${error.message}`);
                    updateProgressText("Error rendering timeline pipeline.");
                } finally {
                    isGenerating = false;
                    generateBtn.disabled = false;
                    if (dropzone) dropzone.style.pointerEvents = "auto";
                    if (voiceSelect) voiceSelect.disabled = false;
                    if (speedSlider) speedSlider.disabled = false;

                    setTimeout(() => {
                        if (pipelineProgress) pipelineProgress.classList.add("hidden");
                        if (progressFillEl) progressFillEl.style.width = "0%";
                    }, 5000);
                }
            });
        }

        if (settingsNavBtn) settingsNavBtn.addEventListener("click", (e) => {
            e.preventDefault();
            openSettings();
        });
        if (settingsOverlay) settingsOverlay.addEventListener("click", closeSettings);
        if (closeSettingsBtn) closeSettingsBtn.addEventListener("click", closeSettings);
        if (cancelSettingsBtn) cancelSettingsBtn.addEventListener("click", closeSettings);

        if (saveSettingsBtn) {
            saveSettingsBtn.addEventListener("click", async () => {
                const geminiVal = geminiInput ? geminiInput.value.trim() : "";
                const deepgramVal = deepgramInput ? deepgramInput.value.trim() : "";
                
                const btnText = saveSettingsBtn.querySelector(".btn-text");
                const originalText = btnText ? btnText.textContent : "Save Keys";
                saveSettingsBtn.disabled = true;
                if (btnText) btnText.innerHTML = `<span class="spinner"></span> Saving...`;
                
                try {
                    await saveApiKeys(geminiVal, deepgramVal);
                    showToast("API keys saved successfully!");
                    closeSettings();
                } catch (err) {
                    showToast(err.message || "Failed to save API keys.", "error");
                } finally {
                    saveSettingsBtn.disabled = false;
                    if (btnText) btnText.textContent = originalText;
                }
            });
        }

        const toggleButtons = document.querySelectorAll(".toggle-password");
        toggleButtons.forEach(btn => {
            btn.addEventListener("click", () => {
                const targetId = btn.getAttribute("data-input");
                const input = document.getElementById(targetId);
                if (input) {
                    if (input.type === "password") {
                        input.type = "text";
                        btn.textContent = "🙈";
                    } else {
                        input.type = "password";
                        btn.textContent = "👁️";
                    }
                }
            });
        });

        // Load saved keys
        await loadInitialKeys();

        // Load video history archives
        await loadHistory(user.id);

        // Setup singleton polling for history refresh every 60 seconds
        setupHistoryPolling(user.id, 60000);
    }

    document.addEventListener("DOMContentLoaded", async () => {
        await initializeDashboard();
    });
}
