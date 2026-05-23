from fastapi import APIRouter

router = APIRouter()

@router.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "app": "NarrateIt API",
        "version": "1.0.0"
    }
