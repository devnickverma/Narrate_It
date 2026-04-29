from supabase import create_client, Client
from utils.config import Config

_supabase: Client | None = None

def get_supabase_client() -> Client:
    """Initialize and return a singleton Supabase client."""
    global _supabase
    if _supabase is None:
        Config.validate()
        _supabase = create_client(Config.SUPABASE_URL, Config.SUPABASE_ANON_KEY)
    return _supabase
