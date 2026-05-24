from fastapi import APIRouter, HTTPException, status, Request
from backend.services.supabase_client import get_supabase_client, get_authenticated_supabase_client
from backend.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/history", tags=["history"])

@router.get("/videos")
async def list_videos(user_id: str, request: Request):
    logger.info(f"Listing videos for user: {user_id}")
    try:
        auth_header = request.headers.get("Authorization")
        jwt_token = None
        if auth_header and auth_header.startswith("Bearer "):
            jwt_token = auth_header.split(" ")[1]

        if jwt_token:
            logger.info("Using authenticated Supabase client for listing videos")
            supabase = get_authenticated_supabase_client(jwt_token)
        else:
            logger.info("Using anonymous Supabase client for listing videos")
            supabase = get_supabase_client()

        files = supabase.storage.from_("videos").list()
        
        normalized_videos = []
        if files:
            for f in files:
                name = f.get("name")
                if name and user_id in name:
                    public_url = supabase.storage.from_("videos").get_public_url(name)
                    normalized_videos.append({
                        "id": f.get("id"),
                        "video_url": public_url or f.get("video_url") or f.get("url"),
                        "title": name or "Generated Narration",
                        "created_at": f.get("created_at")
                    })
                    
        videos = normalized_videos
        logger.info(f"[HISTORY_RESPONSE] {videos}")
        logger.info(f"Number of returned rows: {len(videos)}")
        if videos:
            logger.info(f"Exact keys in first row: {list(videos[0].keys())}")
            
        return {
            "status": "success",
            "videos": videos
        }
    except Exception as e:
        logger.error(f"Failed to fetch videos list for {user_id}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch history: {str(e)}"
        )
