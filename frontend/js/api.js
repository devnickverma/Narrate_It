import { API_BASE_URL } from "./config.js";

/**
 * Trigger OTP authentication code transmission.
 * @param {string} email User email input
 * @returns {Promise<object>} Response payload
 */
async function sendOtp(email) {
    console.log(`[API] Triggering OTP send for: ${email}`);
    try {
        const response = await fetch(`${API_BASE_URL}/auth/otp/send`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email })
        });
        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || "Failed to transmit OTP");
        }
        return await response.json();
    } catch (error) {
        console.error("[API] Error in sendOtp:", error);
        throw error;
    }
}

/**
 * Validate received email OTP code block.
 * @param {string} email User email address
 * @param {string} code OTP validation code token
 * @returns {Promise<object>} Session tokens
 */
async function verifyOtp(email, code) {
    console.log(`[API] Verifying OTP for: ${email}`);
    try {
        const response = await fetch(`${API_BASE_URL}/auth/otp/verify`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email, token: code })
        });
        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || "Invalid verification code");
        }
        return await response.json();
    } catch (error) {
        console.error("[API] Error in verifyOtp:", error);
        throw error;
    }
}

/**
 * Upload PDF and parse text contents/length details.
 * @param {File} file PDF document file descriptor
 * @param {string} userId Active authenticated user uuid
 * @param {AbortSignal} [signal] Optional abort signal descriptor
 * @returns {Promise<object>} Upload structure metadata details
 */
async function uploadPdf(file, userId, signal = null) {
    console.log(`[API] Uploading PDF: ${file.name} for user: ${userId}`);
    try {
        const formData = new FormData();
        formData.append("file", file);
        formData.append("user_id", userId);

        const token = localStorage.getItem("supabase_access_token");
        const headers = {};
        if (token) {
            headers["Authorization"] = `Bearer ${token}`;
        }

        const fetchOptions = {
            method: "POST",
            body: formData,
            headers: headers
        };
        if (signal) fetchOptions.signal = signal;

        const response = await fetch(`${API_BASE_URL}/upload/pdf`, fetchOptions);
        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || "Failed to upload document");
        }
        return await response.json();
    } catch (error) {
        if (error.name === "AbortError") {
            console.warn("[API] uploadPdf request was aborted.");
        }
        console.error("[API] Error in uploadPdf:", error);
        throw error;
    }
}

/**
 * Initiate final narrations & voiceover video assembly.
 * @param {object} payload Generation configurations (pdf_path, voice_name, pace, user_id)
 * @param {AbortSignal} [signal] Optional abort signal descriptor
 * @returns {Promise<object>} Complete video output mappings
 */
async function generateVideo(payload, onProgress = null, signal = null) {
    console.log("[API] Initiating video generation pipeline:", payload);
    try {
        const token = localStorage.getItem("supabase_access_token");
        const headers = { "Content-Type": "application/json" };
        if (token) {
            headers["Authorization"] = `Bearer ${token}`;
        }

        const fetchOptions = {
            method: "POST",
            headers: headers,
            body: JSON.stringify(payload)
        };
        if (signal) fetchOptions.signal = signal;

        const response = await fetch(`${API_BASE_URL}/generate/video`, fetchOptions);
        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || "Video compilation failed");
        }
        
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        
        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            
            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split("\n");
            buffer = lines.pop();
            
            for (const line of lines) {
                if (line.trim()) {
                    let data;
                    try {
                        data = JSON.parse(line);
                    } catch (parseErr) {
                        console.warn("[API] Failed to parse NDJSON line, skipping:", line, parseErr);
                        continue;
                    }
                    
                    if (data.status === "error") {
                        throw new Error(data.message || "Pipeline error");
                    }
                    if (data.status === "success") {
                        return data;
                    }
                    if (data.progress !== undefined && typeof onProgress === "function") {
                        onProgress(data.phase, data.progress, data.message);
                    }
                }
            }
        }
        
        throw new Error("Stream closed before completion");
    } catch (error) {
        if (error.name === "AbortError") {
            console.warn("[API] generateVideo request was aborted.");
        }
        console.error("[API] Error in generateVideo:", error);
        throw error;
    }
}

/**
 * Retrieve public historical video catalogs.
 * @param {string} userId Active authenticated user uuid
 * @param {AbortSignal} [signal] Optional abort signal descriptor
 * @returns {Promise<Array>} Public video collections
 */
async function getHistory(userId, signal = null) {
    console.log(`[API] Requesting history records for user: ${userId}`);
    try {
        const token = localStorage.getItem("supabase_access_token");
        const headers = {};
        if (token) {
            headers["Authorization"] = `Bearer ${token}`;
        }

        const fetchOptions = {
            method: "GET",
            headers: headers
        };
        if (signal) fetchOptions.signal = signal;

        const response = await fetch(`${API_BASE_URL}/history/videos?user_id=${userId}`, fetchOptions);
        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || "Failed to load archives");
        }
        return await response.json();
    } catch (error) {
        if (error.name === "AbortError") {
            console.warn("[API] getHistory request was aborted.");
        }
        console.error("[API] Error in getHistory:", error);
        throw error;
    }
}

/**
 * Save user API keys.
 * @param {string} geminiKey The Gemini key
 * @param {string} deepgramKey The Deepgram key
 * @returns {Promise<object>} Response status object
 */
async function saveApiKeys(geminiKey, deepgramKey) {
    try {
        const token = localStorage.getItem("supabase_access_token");
        const headers = { "Content-Type": "application/json" };
        if (token) {
            headers["Authorization"] = `Bearer ${token}`;
        }

        const response = await fetch(`${API_BASE_URL}/settings/api-keys/save`, {
            method: "POST",
            headers: headers,
            body: JSON.stringify({
                gemini_key: geminiKey,
                deepgram_key: deepgramKey
            })
        });

        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || "Failed to save API keys");
        }
        return await response.json();
    } catch (error) {
        console.error("[API] Error in saveApiKeys:", error);
        throw error;
    }
}

/**
 * Retrieve user API keys (masked).
 * @returns {Promise<object>} Masked API keys configuration
 */
async function getApiKeys() {
    try {
        const token = localStorage.getItem("supabase_access_token");
        const headers = {};
        if (token) {
            headers["Authorization"] = `Bearer ${token}`;
        }

        const response = await fetch(`${API_BASE_URL}/settings/api-keys/get`, {
            method: "GET",
            headers: headers
        });

        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || "Failed to fetch API keys");
        }
        return await response.json();
    } catch (error) {
        console.error("[API] Error in getApiKeys:", error);
        throw error;
    }
}

export {
    sendOtp,
    verifyOtp,
    uploadPdf,
    generateVideo,
    getHistory,
    saveApiKeys,
    getApiKeys
};

