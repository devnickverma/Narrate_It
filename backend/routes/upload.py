from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status
from backend.services.pdf_service import upload_pdf, download_pdf, split_pdf_to_pages
from backend.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/upload", tags=["upload"])

@router.post("/pdf")
async def upload_document(
    user_id: str = Form(...),
    file: UploadFile = File(...)
):
    logger.info(f"Received PDF upload request from user: {user_id}")
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are supported."
        )
        
    local_path = None
    pages = []
    try:
        # Read file bytes
        file_bytes = await file.read()
        
        # Upload to Supabase Storage
        storage_path = upload_pdf(file_bytes, user_id)
        
        # Download locally and split into pages
        local_path = download_pdf(storage_path)
        pages = split_pdf_to_pages(local_path)
        
        return {
            "status": "success",
            "storage_path": storage_path,
            "pages_count": len(pages),
            "pages": [
                {
                    "page_number": p["page_number"],
                    "text_preview": p["text"][:100] + "..." if len(p["text"]) > 100 else p["text"],
                    "text_length": len(p["text"])
                } for p in pages
            ]
        }
    except Exception as e:
        logger.error("Failed to process document upload", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Upload failed: {str(e)}"
        )
    finally:
        # Clean up local downloaded PDF
        if local_path and os.path.exists(local_path):
            try:
                os.remove(local_path)
            except Exception:
                pass
        # Clean up all temporary page images
        for p in pages:
            if isinstance(p, dict) and p.get("image_path") and os.path.exists(p["image_path"]):
                try:
                    os.remove(p["image_path"])
                except Exception:
                    pass
