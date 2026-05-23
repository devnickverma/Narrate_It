import streamlit as st
from services.supabase_client import get_supabase_client
from backend.utils.logger import get_logger
import backend.services.auth_service as backend_auth

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
    # 1. Parse and handle access_token/refresh_token from the JS redirect bridge (Magic Link hash extraction)
    if "access_token" in st.query_params and "refresh_token" in st.query_params:
        access_token = st.query_params["access_token"]
        refresh_token = st.query_params["refresh_token"]
        supabase = get_supabase_client()
        try:
            res = supabase.auth.set_session(access_token, refresh_token)
            if res and res.user:
                st.session_state["user"] = res.user
                logger.info(f"Successfully authenticated user via token callback: {res.user.email}")
        except Exception as e:
            logger.error("Authentication failed during token session restoration", exc_info=True)
            st.error("Authentication failed. Please try again.")
        
        # Clear query params and trigger a clean rerun
        st.query_params.clear()
        st.rerun()

    # 2. Parse and handle PKCE code
    if "code" in st.query_params:
        code = st.query_params["code"]
        logger.info("OAuth code found in URL, exchanging for session.")
        supabase = get_supabase_client()
        try:
            res = supabase.auth.exchange_code_for_session({"auth_code": code})
            if res and res.user:
                st.session_state["user"] = res.user
                logger.info(f"Successfully authenticated user: {res.user.email}")
        except Exception as e:
            logger.error("Authentication failed during code exchange", exc_info=True)
            st.error("Authentication failed. Please try again.")
        
        # Clear the query params and rerun
        st.query_params.clear()
        st.rerun()

def get_current_user():
    import streamlit as st
    from services.supabase_client import get_supabase_client
    from backend.utils.logger import get_logger

    logger = get_logger(__name__)

    # 1. Check session_state first
    if "user" in st.session_state and st.session_state["user"]:
        return st.session_state["user"]

    # 2. Try restoring from Supabase
    supabase = get_supabase_client()

    try:
        session = supabase.auth.get_session()
        if session and hasattr(session, "user") and session.user:
            st.session_state["user"] = session.user
            logger.info(f"Session restored for user via get_session(): {session.user.email}")
            return session.user
    except Exception as e:
        logger.error("Failed to restore session via get_session()", exc_info=True)

    try:
        user_response = supabase.auth.get_user()
        if user_response and hasattr(user_response, "user") and user_response.user:
            st.session_state["user"] = user_response.user
            logger.info(f"Session restored for user via get_user(): {user_response.user.email}")
            return user_response.user
    except Exception as e:
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
    """Send a passwordless OTP code to the user's email using the unified backend auth service."""
    return backend_auth.send_otp_code(email)

def verify_otp_code(email: str, token: str):
    """Verify the OTP code token via backend auth service and assign user state locally if valid."""
    success, result = backend_auth.verify_otp_code(email, token)
    if success:
        # Check actual returned structure
        user_obj = None
        if hasattr(result, "user") and result.user:
            user_obj = result.user
        elif hasattr(result, "session") and result.session and hasattr(result.session, "user") and result.session.user:
            user_obj = result.session.user
            
        if user_obj:
            st.session_state["user"] = user_obj
            logger.info(f"Successfully verified and authenticated user via backend proxy: {user_obj.email}")
            return True, "Login successful!"
            
    # Handle failure case
    logger.error("Authentication failed during OTP code confirmation via backend proxy.")
    return False, str(result)
