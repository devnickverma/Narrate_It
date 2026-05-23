from fastapi import APIRouter, HTTPException, status
from backend.services.supabase_client import get_supabase_client
from backend.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/history", tags=["history"])

@router.get("/videos")
async def list_videos(user_id: str):
    logger.info(f"Listing videos for user: {user_id}")
    try:
        supabase = get_supabase_client()
        files = supabase.storage.from_("videos").list()
        
        user_videos = []
        if files:
            for f in files:
                name = f.get("name")
                if name and user_id in name:
                    public_url = supabase.storage.from_("videos").get_public_url(name)
                    user_videos.append({
                        "name": name,
                        "url": public_url,
                        "created_at": f.get("created_at")
                    })
                    
        return {
            "status": "success",
            "videos": user_videos
        }
    except Exception as e:
        logger.error(f"Failed to fetch videos list for {user_id}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch history: {str(e)}"
        )
