import streamlit as st
from services.supabase_client import get_supabase_client
from utils.logger import get_logger

logger = get_logger(__name__)

def login_with_google():
    """Trigger Supabase Google OAuth flow."""
    logger.info("Initiating Google OAuth login flow.")
    supabase = get_supabase_client()
    
    # Generate the OAuth URL using Supabase client
    res = supabase.auth.sign_in_with_oauth({
        "provider": "google",
        "options": {
            "skip_browser_redirect": True,
            "redirect_to": "http://localhost:8501"
        }
    })
    
    if res and res.url:
        logger.info("Redirecting to OAuth provider.")
        st.markdown(f'<meta http-equiv="refresh" content="0;url={res.url}">', unsafe_allow_html=True)
    else:
        logger.error("Failed to initiate Google login flow.")
        st.error("Failed to initiate Google login flow.")

def handle_oauth_callback():
    """Handle the OAuth callback and exchange code or token for session."""
    logger.debug(f"[DEBUG-AUTH] handle_oauth_callback called. st.query_params keys: {list(st.query_params.keys())}")
    
    # 1. Parse and handle access_token/refresh_token from the JS redirect bridge (Magic Link hash extraction)
    if "access_token" in st.query_params and "refresh_token" in st.query_params:
        access_token = st.query_params["access_token"]
        refresh_token = st.query_params["refresh_token"]
        logger.debug(f"[DEBUG-AUTH] access_token exists: {bool(access_token)}, refresh_token exists: {bool(refresh_token)}")
        logger.debug("[DEBUG-AUTH] Attempting session restore via set_session")
        supabase = get_supabase_client()
        try:
            res = supabase.auth.set_session(access_token, refresh_token)
            logger.debug(f"[DEBUG-AUTH] set_session returned: {res}")
            if res and res.user:
                st.session_state["user"] = res.user
                logger.debug(f"[DEBUG-AUTH] st.session_state keys after mapping: {list(st.session_state.keys())}")
                logger.debug(f"[DEBUG-AUTH] Authenticated email: {res.user.email}")
                logger.info(f"Successfully authenticated user via token callback: {res.user.email}")
            else:
                logger.debug("[DEBUG-AUTH] set_session response or user is None/empty")
        except Exception as e:
            logger.error("[DEBUG-AUTH] Exception occurred during set_session", exc_info=True)
            logger.error("Authentication failed during token session restoration", exc_info=True)
            st.error("Authentication failed. Please try again.")
        
        # Clear query params and trigger a clean rerun
        logger.debug("[DEBUG-AUTH] Triggering rerun after auth restore (tokens)")
        st.query_params.clear()
        st.rerun()

    # 2. Parse and handle PKCE code
    if "code" in st.query_params:
        code = st.query_params["code"]
        logger.debug(f"[DEBUG-AUTH] PKCE code exists: {bool(code)}")
        logger.debug("[DEBUG-AUTH] Attempting PKCE session exchange")
        logger.info("OAuth code found in URL, exchanging for session.")
        supabase = get_supabase_client()
        try:
            res = supabase.auth.exchange_code_for_session({"auth_code": code})
            logger.debug(f"[DEBUG-AUTH] exchange_code_for_session returned: {res}")
            if res and res.user:
                st.session_state["user"] = res.user
                logger.debug(f"[DEBUG-AUTH] st.session_state keys after mapping: {list(st.session_state.keys())}")
                logger.debug(f"[DEBUG-AUTH] Authenticated email: {res.user.email}")
                logger.info(f"Successfully authenticated user: {res.user.email}")
            else:
                logger.debug("[DEBUG-AUTH] exchange_code_for_session response or user is None/empty")
        except Exception as e:
            logger.error("[DEBUG-AUTH] Exception occurred during PKCE exchange", exc_info=True)
            logger.error("Authentication failed during code exchange", exc_info=True)
            st.error("Authentication failed. Please try again.")
        
        # Clear the query params and rerun
        logger.debug("[DEBUG-AUTH] Triggering rerun after auth restore (code)")
        st.query_params.clear()
        st.rerun()

def get_current_user():
    import streamlit as st
    from services.supabase_client import get_supabase_client
    from utils.logger import get_logger

    logger = get_logger(__name__)

    # 1. Check session_state first
    logger.debug(f"[DEBUG-AUTH] get_current_user check - session_state 'user' exists: {'user' in st.session_state and bool(st.session_state['user'])}")
    if "user" in st.session_state and st.session_state["user"]:
        return st.session_state["user"]

    # 2. Try restoring from Supabase
    supabase = get_supabase_client()

    try:
        session = supabase.auth.get_session()
        logger.debug(f"[DEBUG-AUTH] get_session() returned: {session}")
        if session and hasattr(session, "user") and session.user:
            st.session_state["user"] = session.user
            logger.info(f"Session restored for user via get_session(): {session.user.email}")
            return session.user
    except Exception as e:
        logger.error("[DEBUG-AUTH] Exception occurred during get_session()", exc_info=True)
        logger.error("Failed to restore session via get_session()", exc_info=True)

    try:
        user_response = supabase.auth.get_user()
        logger.debug(f"[DEBUG-AUTH] get_user() returned: {user_response}")
        if user_response and hasattr(user_response, "user") and user_response.user:
            st.session_state["user"] = user_response.user
            logger.info(f"Session restored for user via get_user(): {user_response.user.email}")
            return user_response.user
    except Exception as e:
        logger.error("[DEBUG-AUTH] Exception occurred during get_user()", exc_info=True)
        logger.error("Failed to restore session via get_user()", exc_info=True)

    return None

def logout():
    supabase = get_supabase_client()
    try:
        supabase.auth.sign_out()
    except:
        pass
    st.session_state.clear()
    st.rerun()

def send_otp_code(email: str):
    """Send a passwordless OTP code to the user's email using Supabase."""
    logger.info(f"Initiating OTP delivery for email: {email}")
    supabase = get_supabase_client()
    try:
        supabase.auth.sign_in_with_otp({
            "email": email,
            "options": {
                "should_create_user": True
            }
        })
        logger.info(f"Successfully requested OTP email for {email}")
        return True, "One-time code sent successfully! Please check your email inbox."
    except Exception as e:
        logger.error(f"Failed to deliver OTP code for {email}", exc_info=True)
        return False, f"Delivery failed: {str(e)}"

def verify_otp_code(email: str, token: str):
    """Verify the OTP code token via Supabase."""
    logger.info(f"Verifying OTP code for user: {email}")
    supabase = get_supabase_client()
    try:
        res = supabase.auth.verify_otp({
            "email": email,
            "token": token,
            "type": "email"
        })
        if res and res.user:
            st.session_state["user"] = res.user
            logger.info(f"Successfully verified and authenticated user: {res.user.email}")
            return True, "Login successful!"
        else:
            logger.error("Authentication failed during OTP code confirmation - no user returned.")
            return False, "Failed to authenticate. Try again."
    except Exception as e:
        logger.error(f"OTP verification failed for user {email}", exc_info=True)
        return False, f"Verification failed: {str(e)}"

