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
    const googleLoginBtn = document.getElementById("google-login-btn");
    const errorMessage = document.getElementById("error-message");

    let isOtpSent = false;
    let pendingEmail = "";
    let cooldownTimer = null;
    let cooldownSeconds = 30;

    // ==================================================
    // 1. URL Hash Callback Parsing (Supabase Magic Link / Google Redirects)
    // ==================================================
    if (window.location.hash) {
        console.log("[AUTH] URL hash fragment callback detected. Processing Supabase session credentials...");
        try {
            const hash = window.location.hash.substring(1);
            const params = new URLSearchParams(hash);

            const accessToken = params.get("access_token");
            const refreshToken = params.get("refresh_token");
            const expiresIn = params.get("expires_in");
            const tokenType = params.get("token_type");

            if (accessToken) {
                console.log("[AUTH] Successfully extracted access_token from hash fragment.");
                
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
                    console.log("[AUTH] Successfully decoded user metadata from JWT claims:", userProfile);
                } else {
                    localStorage.setItem("supabase_user", JSON.stringify({ id: null, email: "oauth_user@narrate.it" }));
                }

                console.log("[AUTH] Auth credentials cached successfully. Clearing hash from address bar...");
                // Remove hash fragment cleanly from URL bar to prevent replay confusion
                window.history.replaceState(null, null, window.location.pathname);

                // Redirect cleanly to workspace dashboard
                console.log("[AUTH] Redirecting user directly to workspace dashboard.html");
                window.location.href = "dashboard.html";
                return;
            }
        } catch (e) {
            console.error("[AUTH] Error processing URL hash callback:", e);
            showError("Authentication failed during hash parsing callback.");
        }
    }

    // ==================================================
    // 2. Active Session Restoration check
    // ==================================================
    if (isSessionValid()) {
        const isDashboard = window.location.pathname.endsWith("dashboard.html");
        console.log("[AUTH] Auth validation passed. Session is valid. Is Dashboard page:", isDashboard);
        if (!isDashboard) {
            console.log("[AUTH] Redirecting to dashboard...");
            window.location.href = "dashboard.html";
            return;
        }
    } else {
        // If expired or invalid, auto-purge lingering tokens to avoid half-states
        if (localStorage.getItem("supabase_access_token")) {
            console.log("[AUTH] Lingering expired session identified. Flushing auth variables.");
            localStorage.removeItem("supabase_access_token");
            localStorage.removeItem("supabase_refresh_token");
            localStorage.removeItem("supabase_expires_at");
            localStorage.removeItem("supabase_user");
        }
    }

    // Google OAuth Handler
    if (googleLoginBtn) {
        googleLoginBtn.addEventListener("click", () => {
            console.log("[AUTH] Initiating third-party Google OAuth redirection...");
            errorMessage.classList.add("hidden");
            
            // Get root execution host for local development redirections
            const currentHost = window.location.origin + window.location.pathname;
            console.log("[AUTH] Setting callback redirection landing URL to:", currentHost);
            
            const authUrl = `https://usnxhtmgkdbrcvlysfsv.supabase.co/auth/v1/authorize?provider=google&redirect_to=${encodeURIComponent(currentHost)}`;
            window.location.href = authUrl;
        });
    }

    // Email Passwordless OTP submit handler
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

            submitBtn.disabled = true;

            try {
                if (!isOtpSent) {
                    console.log(`[AUTH] [REQUEST] Requesting OTP code transmission for: ${email}`);
                    submitBtn.textContent = "Transmitting...";
                    
                    const response = await sendOtp(email);
                    console.log("[AUTH] [RESPONSE] sendOtp response:", response);
                    
                    if (response && response.otp_required) {
                        isOtpSent = true;
                        pendingEmail = email;
                        emailInput.disabled = true;
                        otpSection.classList.remove("hidden");
                        otpInput.required = true;
                        otpInput.focus();
                        
                        startResendCooldown();
                    } else {
                        // Magic link mode: Show success state UI!
                        // Hide login form inputs and Google login elements
                        const inputGroup = loginForm.querySelector(".input-group:not(#otp-section)");
                        if (inputGroup) inputGroup.classList.add("hidden");
                        submitBtn.classList.add("hidden");
                        
                        const googleBtn = document.getElementById("google-login-btn");
                        if (googleBtn) googleBtn.classList.add("hidden");
                        
                        const divider = document.querySelector(".divider");
                        if (divider) divider.classList.add("hidden");
                        
                        // Show success state
                        const successState = document.getElementById("success-state");
                        if (successState) {
                            successState.classList.remove("hidden");
                            const successMsg = document.getElementById("success-message");
                            if (successMsg) {
                                successMsg.textContent = response.message || "Magic login link sent to your email";
                            }
                        } else {
                            // Fallback if success-state element is missing
                            showError("Magic login link sent to your email! Please check your inbox.");
                        }
                    }
                } else {
                    const code = otpInput.value.trim();
                    if (!code || code.length < 6) {
                        showError("Please enter a valid 6-digit OTP verification code.");
                        submitBtn.disabled = false;
                        return;
                    }

                    console.log(`[AUTH] [REQUEST] Verifying OTP token: ${code} for email: ${pendingEmail}`);
                    submitBtn.textContent = "Authorizing Access...";
                    
                    const response = await verifyOtp(pendingEmail, code);
                    console.log("[AUTH] [RESPONSE] verifyOtp response:", response);

                    if (response.access_token) {
                        submitBtn.classList.remove("btn-primary", "btn-verify");
                        submitBtn.style.background = "linear-gradient(135deg, #10B981 0%, #059669 100%)";
                        submitBtn.textContent = "Authorized! Redirecting...";
                        
                        // Default token duration: 1 hour (3600 seconds)
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
                        
                        console.log("[AUTH] Passwordless session validated successfully. Triggering Dashboard redirect.");
                        setTimeout(() => {
                            window.location.href = "dashboard.html";
                        }, 1000);
                    } else {
                        throw new Error("Credentials omitted inside verify OTP callback response.");
                    }
                }
            } catch (error) {
                console.error("[AUTH] Authentication loop failed:", error);
                showError(error.message || "Authentication failed. Try again.");
                submitBtn.disabled = false;
                
                if (submitBtn.textContent === "Transmitting...") {
                    submitBtn.textContent = "Get Verification Link";
                } else if (submitBtn.textContent === "Authorizing Access...") {
                    submitBtn.textContent = "Verify & Access";
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
                submitBtn.textContent = "Verify & Access";
                
                let resendHint = document.getElementById("resend-hint");
                if (!resendHint) {
                    resendHint = document.createElement("p");
                    resendHint.id = "resend-hint";
                    resendHint.style.fontSize = "0.8rem";
                    resendHint.style.marginTop = "12px";
                    resendHint.style.color = "var(--text-muted)";
                    resendHint.innerHTML = "Didn't receive a code? <span style='color: var(--primary); cursor: pointer; text-decoration: underline;' id='resend-trigger'>Resend OTP</span>";
                    loginForm.appendChild(resendHint);
                    
                    document.getElementById("resend-trigger").addEventListener("click", () => {
                        isOtpSent = false;
                        emailInput.disabled = false;
                        otpSection.classList.add("hidden");
                        otpInput.value = "";
                        resendHint.remove();
                        submitBtn.textContent = "Get Verification Link";
                        submitBtn.click();
                    });
                }
            } else {
                submitBtn.textContent = `Verify & Access (${cooldownSeconds}s)`;
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
    console.log("[AUTH] Logging out user. Flushing cached persistent localStorage tokens.");
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
    
    console.log("[AUTH] Flush sequence completed. Redirecting to index.html login page.");
    window.location.href = "index.html";
}

window.logout = logout;
export { logout, isSessionValid };

