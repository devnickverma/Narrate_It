import { sendOtp, verifyOtp } from "./api.js";

/**
 * Pure helper function to decode user info from JWT access token.
 * @param {string} token Supabase standard JWT access token
 * @returns {object|null} Decoded token payload claims or null
 */
function parseJwt(token) {
    try {
        const base64Url = token.split('.')[1];
        const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
        const jsonPayload = decodeURIComponent(atob(base64).split('').map(function(c) {
            return '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2);
        }).join(''));
        return JSON.parse(jsonPayload);
    } catch (e) {
        console.error("[AUTH] Failed to decode JWT access token:", e);
        return null;
    }
}

/**
 * Validates whether the locally stored session is present and unexpired.
 * @returns {boolean} True if active session is unexpired
 */
function isSessionValid() {
    const token = localStorage.getItem("supabase_access_token");
    const user = localStorage.getItem("supabase_user");
    const expiresAt = localStorage.getItem("supabase_expires_at");

    if (!token || !user) {
        return false;
    }

    if (expiresAt) {
        const expiresTime = parseInt(expiresAt, 10);
        if (Date.now() > expiresTime) {
            console.warn("[AUTH] Locally cached session has expired.");
            return false;
        }
    }
    return true;
}

document.addEventListener("DOMContentLoaded", () => {
    const loginForm = document.getElementById("login-form");
    const emailInput = document.getElementById("email-input");
    const otpSection = document.getElementById("otp-section");
    const otpInput = document.getElementById("otp-input");
    const submitBtn = document.getElementById("submit-btn");
    const errorMessage = document.getElementById("error-message");

    let isOtpSent = false;
    let pendingEmail = "";
    let cooldownTimer = null;
    let cooldownSeconds = 30;

    // Store original button text for restoration
    const defaultBtnText = "Send Login Link";

    // ==================================================
    // 1. URL Hash Callback Parsing (Supabase Magic Link Redirects)
    // ==================================================
    if (window.location.hash) {
        console.log("[AUTH] URL hash fragment callback detected. Processing session credentials...");
        try {
            const hash = window.location.hash.substring(1);
            const params = new URLSearchParams(hash);

            const accessToken = params.get("access_token");
            const refreshToken = params.get("refresh_token");
            const expiresIn = params.get("expires_in");

            if (accessToken) {
                console.log("[AUTH] Login link confirmed. Establishing session...");
                
                // Set precise expiration timestamp
                const duration = expiresIn ? parseInt(expiresIn, 10) : 3600;
                const expiresAt = Date.now() + duration * 1000;
                localStorage.setItem("supabase_access_token", accessToken);
                localStorage.setItem("supabase_expires_at", expiresAt.toString());
                
                if (refreshToken) {
                    localStorage.setItem("supabase_refresh_token", refreshToken);
                }

                // Decode user metadata from JWT payload claims
                const decoded = parseJwt(accessToken);
                if (decoded) {
                    const userProfile = {
                        id: decoded.sub,
                        email: decoded.email
                    };
                    localStorage.setItem("supabase_user", JSON.stringify(userProfile));
                    console.log("[AUTH] User session established:", userProfile.email);
                } else {
                    localStorage.setItem("supabase_user", JSON.stringify({ id: null, email: "user@narrate.it" }));
                }

                // Remove hash fragment cleanly from URL bar
                window.history.replaceState(null, null, window.location.pathname);

                // Redirect to workspace dashboard
                console.log("[AUTH] Redirecting to workspace...");
                window.location.href = "dashboard.html";
                return;
            }
        } catch (e) {
            console.error("[AUTH] Error processing login callback:", e);
            showError("Something went wrong. Please try again.");
        }
    }

    // ==================================================
    // 2. Active Session Restoration check
    // ==================================================
    if (isSessionValid()) {
        const isDashboard = window.location.pathname.endsWith("dashboard.html");
        console.log("[AUTH] Active session found. Dashboard page:", isDashboard);
        if (!isDashboard) {
            console.log("[AUTH] Redirecting to workspace...");
            window.location.href = "dashboard.html";
            return;
        }
    } else {
        // If expired or invalid, auto-purge lingering tokens
        if (localStorage.getItem("supabase_access_token")) {
            console.log("[AUTH] Expired session found. Clearing credentials.");
            localStorage.removeItem("supabase_access_token");
            localStorage.removeItem("supabase_refresh_token");
            localStorage.removeItem("supabase_expires_at");
            localStorage.removeItem("supabase_user");
        }
    }

    // ==================================================
    // 3. Email Magic Link Submit Handler
    // ==================================================
    if (loginForm) {
        loginForm.addEventListener("submit", async (e) => {
            e.preventDefault();
            errorMessage.classList.add("hidden");
            errorMessage.textContent = "";
            
            const email = emailInput.value.trim();
            if (!email) {
                showError("Please enter a valid email address.");
                return;
            }

            // Disable button and show loading state
            submitBtn.disabled = true;

            try {
                if (!isOtpSent) {
                    console.log(`[AUTH] Sending login link to: ${email}`);
                    submitBtn.textContent = "Sending Link...";
                    
                    const response = await sendOtp(email);
                    console.log("[AUTH] Login link response:", response);
                    
                    if (response && response.otp_required) {
                        // Backend requires code entry — show code input
                        isOtpSent = true;
                        pendingEmail = email;
                        emailInput.disabled = true;
                        otpSection.classList.remove("hidden");
                        otpInput.required = true;
                        otpInput.focus();
                        submitBtn.disabled = false;
                        submitBtn.textContent = "Continue";
                        
                        startResendCooldown();
                    } else {
                        // Magic link mode: Show success state
                        console.log("[AUTH] Login link sent successfully");
                        
                        const inputGroup = loginForm.querySelector(".input-group:not(#otp-section)");
                        if (inputGroup) inputGroup.classList.add("hidden");
                        submitBtn.classList.add("hidden");
                        
                        // Show success state
                        const successState = document.getElementById("success-state");
                        if (successState) {
                            successState.classList.remove("hidden");
                            const successMsg = document.getElementById("success-message");
                            if (successMsg) {
                                successMsg.textContent = response.message || "We've sent you a secure login link. Open your inbox and click the link to access your workspace.";
                            }
                        }
                    }
                } else {
                    // Code verification path
                    const code = otpInput.value.trim();
                    if (!code || code.length < 6) {
                        showError("Please enter the 6-digit code from your email.");
                        submitBtn.disabled = false;
                        return;
                    }

                    console.log(`[AUTH] Verifying login code for: ${pendingEmail}`);
                    submitBtn.textContent = "Signing in...";
                    
                    const response = await verifyOtp(pendingEmail, code);
                    console.log("[AUTH] Login code verified successfully");

                    if (response.access_token) {
                        submitBtn.style.background = "linear-gradient(135deg, #10B981 0%, #059669 100%)";
                        submitBtn.textContent = "Welcome! Redirecting...";
                        
                        const duration = 3600;
                        const expiresAt = Date.now() + duration * 1000;
                        
                        localStorage.setItem("supabase_access_token", response.access_token);
                        localStorage.setItem("supabase_expires_at", expiresAt.toString());
                        if (response.refresh_token) {
                            localStorage.setItem("supabase_refresh_token", response.refresh_token);
                        }
                        if (response.user) {
                            localStorage.setItem("supabase_user", JSON.stringify(response.user));
                        }
                        
                        console.log("[AUTH] Session established. Redirecting to workspace.");
                        setTimeout(() => {
                            window.location.href = "dashboard.html";
                        }, 1000);
                    } else {
                        throw new Error("Unable to establish session. Please try again.");
                    }
                }
            } catch (error) {
                console.error("[AUTH] Login link request failed:", error);
                showError(error.message || "Something went wrong. Please try again.");
                submitBtn.disabled = false;
                
                // Restore button text based on current state
                if (!isOtpSent) {
                    submitBtn.textContent = defaultBtnText;
                } else {
                    submitBtn.textContent = "Continue";
                }
            }
        });
    }

    function startResendCooldown() {
        cooldownSeconds = 30;
        submitBtn.disabled = true;
        
        if (cooldownTimer) clearInterval(cooldownTimer);
        
        cooldownTimer = setInterval(() => {
            cooldownSeconds--;
            if (cooldownSeconds <= 0) {
                clearInterval(cooldownTimer);
                submitBtn.disabled = false;
                submitBtn.textContent = "Continue";
                
                let resendHint = document.getElementById("resend-hint");
                if (!resendHint) {
                    resendHint = document.createElement("p");
                    resendHint.id = "resend-hint";
                    resendHint.style.fontSize = "0.8rem";
                    resendHint.style.marginTop = "12px";
                    resendHint.style.color = "var(--text-muted)";
                    resendHint.innerHTML = "Didn't receive a code? <span style='color: var(--primary); cursor: pointer; text-decoration: underline;' id='resend-trigger'>Resend</span>";
                    loginForm.appendChild(resendHint);
                    
                    document.getElementById("resend-trigger").addEventListener("click", () => {
                        isOtpSent = false;
                        emailInput.disabled = false;
                        otpSection.classList.add("hidden");
                        otpInput.value = "";
                        resendHint.remove();
                        submitBtn.textContent = defaultBtnText;
                        submitBtn.click();
                    });
                }
            } else {
                submitBtn.textContent = `Continue (${cooldownSeconds}s)`;
            }
        }, 1000);
    }

    function showError(message) {
        if (errorMessage) {
            errorMessage.textContent = message;
            errorMessage.classList.remove("hidden");
            errorMessage.classList.add("shake");
            setTimeout(() => errorMessage.classList.remove("shake"), 500);
        }
    }
});

// Global standard logout sequence
function logout() {
    console.log("[AUTH] Logging out. Clearing session.");
    if (typeof window.abortActiveOperations === "function") {
        try {
            window.abortActiveOperations();
        } catch (e) {
            console.error("[AUTH] Error during operations abort cleanup:", e);
        }
    }
    localStorage.removeItem("supabase_access_token");
    localStorage.removeItem("supabase_refresh_token");
    localStorage.removeItem("supabase_expires_at");
    localStorage.removeItem("supabase_user");
    
    console.log("[AUTH] Session cleared. Redirecting to login.");
    window.location.href = "index.html";
}

window.logout = logout;
export { logout, isSessionValid };
