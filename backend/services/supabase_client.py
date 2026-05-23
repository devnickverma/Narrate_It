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
