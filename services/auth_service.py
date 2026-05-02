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
    """Handle the OAuth callback and exchange code for session."""
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
    from utils.logger import get_logger

    logger = get_logger(__name__)

    # 1. Check session_state first
    if "user" in st.session_state and st.session_state["user"]:
        return st.session_state["user"]

    # 2. Try restoring from Supabase
    supabase = get_supabase_client()

    try:
        session = supabase.auth.get_session()

        # ✅ CORRECT CHECK (IMPORTANT)
        if session and hasattr(session, "user") and session.user:
            st.session_state["user"] = session.user
            logger.info(f"Session restored for user: {session.user.email}")
            return session.user

    except Exception as e:
        logger.error("Failed to restore session", exc_info=True)

    return None

def logout():
    supabase = get_supabase_client()
    try:
        supabase.auth.sign_out()
    except:
        pass
    st.session_state.clear()
    st.rerun()
