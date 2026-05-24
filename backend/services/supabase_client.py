from supabase import create_client, Client
from backend.config.settings import settings

_supabase: Client | None = None

def get_supabase_client() -> Client:
    """Initialize and return a singleton Supabase client."""
    global _supabase
    if _supabase is None:
        settings.validate()
        _supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)
    return _supabase

def get_authenticated_supabase_client(jwt_token: str) -> Client:
    """Initialize and return a request-scoped Supabase client bound to the authenticated JWT session."""
    settings.validate()
    client = create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)
    
    # Bind user session
    try:
        client.auth.set_session(access_token=jwt_token, refresh_token="")
    except Exception:
        pass
        
    # Explicitly propagate the Authorization header to sub-clients to bypass any SDK limitations
    try:
        client.postgrest.auth(jwt_token)
    except Exception:
        pass
        
    try:
        client.storage.session.headers["Authorization"] = f"Bearer {jwt_token}"
    except Exception:
        pass
        
    return client

