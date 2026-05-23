import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Settings:
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
    SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")
    
    # FastAPI specific configurations
    APP_NAME = "NarrateIt API"
    DEBUG = os.getenv("DEBUG", "False").lower() in ("true", "1", "t")
    PORT = int(os.getenv("PORT", 8000))
    HOST = os.getenv("HOST", "127.0.0.1")

    @classmethod
    def validate(cls):
        if not cls.SUPABASE_URL or not cls.SUPABASE_ANON_KEY:
            raise ValueError("SUPABASE_URL and SUPABASE_ANON_KEY must be set in the environment.")

settings = Settings()
settings.validate()
