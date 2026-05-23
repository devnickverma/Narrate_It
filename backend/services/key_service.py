from backend.services.supabase_client import get_supabase_client
from backend.utils.crypto import encrypt, decrypt
from datetime import datetime, timezone
from backend.utils.logger import get_logger

logger = get_logger(__name__)

def save_api_keys(user_id: str, gemini_key: str, deepgram_key: str):
    """Encrypts and saves API keys for a user."""
    logger.info(f"Saving API keys for user_id: {user_id}")
    supabase = get_supabase_client()
    
    gemini_enc, iv1 = encrypt(gemini_key) if gemini_key else ("", "")
    deepgram_enc, iv2 = encrypt(deepgram_key) if deepgram_key else ("", "")
    
    # Store both IVs securely in the iv column, separated by colon
    combined_iv = f"{iv1}:{iv2}"
    
    data = {
        "user_id": user_id,
        "gemini_key_encrypted": gemini_enc,
        "deepgram_key_encrypted": deepgram_enc,
        "iv": combined_iv,
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    
    try:
        # Check if user already has keys to decide between insert/update
        response = supabase.table("api_keys").select("id").eq("user_id", user_id).execute()
        
        if response.data:
            # Update existing record
            row_id = response.data[0]["id"]
            supabase.table("api_keys").update(data).eq("id", row_id).execute()
            logger.info("Successfully updated existing API keys.")
        else:
            # Insert new record
            supabase.table("api_keys").insert(data).execute()
            logger.info("Successfully inserted new API keys.")
    except Exception as e:
        logger.error("Failed to save API keys to database", exc_info=True)
        raise Exception("Failed to save API keys to database.")

def get_api_keys(user_id: str) -> dict:
    """Fetches and decrypts API keys for a user."""
    logger.info(f"Fetching API keys for user_id: {user_id}")
    supabase = get_supabase_client()
    
    try:
        response = supabase.table("api_keys").select("*").eq("user_id", user_id).execute()
        
        if not response.data:
            logger.info("No API keys found for user.")
            return {"gemini_key": None, "deepgram_key": None}
            
        row = response.data[0]
        iv_str = row.get("iv", "")
        parts = iv_str.split(":") if iv_str else []
        
        iv1 = parts[0] if len(parts) > 0 else ""
        iv2 = parts[1] if len(parts) > 1 else ""
        
        gemini_key = None
        if row.get("gemini_key_encrypted") and iv1:
            gemini_key = decrypt(row["gemini_key_encrypted"], iv1)
            
        deepgram_key = None
        if row.get("deepgram_key_encrypted") and iv2:
            deepgram_key = decrypt(row["deepgram_key_encrypted"], iv2)
            
        logger.info("Successfully decrypted API keys.")
        return {"gemini_key": gemini_key, "deepgram_key": deepgram_key}
    except Exception as e:
        logger.error("Failed to fetch or decrypt API keys", exc_info=True)
        raise Exception("Failed to fetch API keys.")

def has_api_keys(user_id: str) -> bool:
    """Checks if a user has configured API keys."""
    supabase = get_supabase_client()
    try:
        response = supabase.table("api_keys").select("id").eq("user_id", user_id).execute()
        return len(response.data) > 0
    except Exception as e:
        logger.error("Failed to check for API keys presence", exc_info=True)
        return False
