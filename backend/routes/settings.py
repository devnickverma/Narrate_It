from fastapi import APIRouter, HTTPException, status, Request
from pydantic import BaseModel
from backend.services.key_service import save_user_api_keys, get_user_api_keys
from backend.services.supabase_client import get_authenticated_supabase_client
from backend.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/settings", tags=["settings"])

class ApiKeysPayload(BaseModel):
    gemini_key: str
    deepgram_key: str

def get_auth_context_from_header(request: Request) -> tuple[str, str]:
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        logger.warning("Missing or invalid Authorization header in settings request")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header"
        )
    jwt_token = auth_header.split(" ")[1]
    
    try:
        client = get_authenticated_supabase_client(jwt_token)
        response = client.auth.get_user()
        if response and response.user:
            return response.user.id, jwt_token
        raise Exception("User object absent from Supabase auth response")
    except Exception as e:
        logger.error("Failed to authenticate JWT with Supabase", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired session token: {str(e)}"
        )

@router.post("/api-keys/save")
async def save_keys_endpoint(request: Request, payload: ApiKeysPayload):
    user_id, jwt_token = get_auth_context_from_header(request)
    logger.info(f"Received request to save API keys for user: {user_id}")
    try:
        # Load existing keys first to preserve unmodified keys (if they are sent as masked)
        existing_keys = get_user_api_keys(user_id, jwt_token)
        
        gemini_to_save = payload.gemini_key
        if "*" in gemini_to_save:
            gemini_to_save = existing_keys.get("gemini_key") or ""
            
        deepgram_to_save = payload.deepgram_key
        if "*" in deepgram_to_save:
            deepgram_to_save = existing_keys.get("deepgram_key") or ""
            
        save_user_api_keys(user_id, gemini_to_save, deepgram_to_save, jwt_token)
        return {"status": "success", "message": "API keys saved successfully"}
    except Exception as e:
        logger.error(f"Failed to save API keys: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save API keys: {str(e)}"
        )

@router.get("/api-keys/get")
async def get_keys_endpoint(request: Request):
    user_id, jwt_token = get_auth_context_from_header(request)
    logger.info(f"Received request to get API keys for user: {user_id}")
    try:
        keys = get_user_api_keys(user_id, jwt_token)
        gemini_raw = keys.get("gemini_key")
        deepgram_raw = keys.get("deepgram_key")
        
        gemini_masked = ""
        if gemini_raw:
            gemini_masked = gemini_raw[:4] + "*" * 16 if len(gemini_raw) > 4 else "****************"
            
        deepgram_masked = ""
        if deepgram_raw:
            deepgram_masked = deepgram_raw[:4] + "*" * 16 if len(deepgram_raw) > 4 else "****************"
            
        return {
            "status": "success",
            "gemini_key": gemini_masked,
            "deepgram_key": deepgram_masked
        }
    except Exception as e:
        logger.error(f"Failed to get API keys: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch API keys: {str(e)}"
        )
