import os
import time
from fastapi import APIRouter, HTTPException, status
from backend.models.generate import GenerationRequest
from backend.services.pdf_service import download_pdf, split_pdf_to_pages
from backend.services.narration_service import generate_narration
from backend.services.tts_service import generate_audio
from backend.services.video_service import generate_video
from backend.services.supabase_client import get_supabase_client
from backend.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/generate", tags=["generate"])

@router.post("/video")
async def generate_video_pipeline(payload: GenerationRequest):
    logger.info(f"Triggering video generation pipeline for user: {payload.user_id} with PDF: {payload.pdf_path}")
    
    local_pdf = None
    pages_to_clean = []
    
    try:
        # 1. Download PDF
        try:
            local_pdf = download_pdf(payload.pdf_path)
        except Exception as e:
            logger.error(f"Failed to download PDF {payload.pdf_path}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"PDF not found or download failed: {str(e)}"
            )
            
        # 2. Split PDF into pages
        try:
            pages = split_pdf_to_pages(local_pdf)
            pages_to_clean = pages # Keep references to temp page images for cleanup
        except Exception as e:
            logger.error("Failed to parse and split PDF", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"PDF split failed: {str(e)}"
            )
            
        # 3. Generate Narrations & Audios for each page
        narrations_list = []
        for page in pages:
            pn = page["page_number"]
            logger.info(f"Processing page {pn}/{len(pages)}")
            
            # Generate script
            script = generate_narration(
                page_text=page["text"],
                context=None,
                user_id=payload.user_id,
                image_path=page["image_path"]
            )
            
            # Translate voice model/speed configuration
            voice = payload.voice_name or "aura-asteria-en"
            speed = 1.0
            if payload.pace == "slow":
                speed = 0.85
            elif payload.pace == "fast":
                speed = 1.15
                
            # Generate Audio via Deepgram
            audio_path = generate_audio(
                text=script,
                user_id=payload.user_id,
                page=pn,
                voice_model=voice,
                speed=speed
            )
            
            # Save audio path reference for proper cleanup in finally block
            page["audio_path"] = audio_path
            
            narrations_list.append({
                "page": pn,
                "text": script,
                "image_path": page["image_path"],
                "audio_path": audio_path
            })
            
            # Sleep briefly to be respectful to APIs
            time.sleep(0.5)
            
        # 4. Render Final Video
        try:
            video_path = generate_video(narrations_list, payload.user_id)
        except Exception as e:
            logger.error("Failed to render video clips", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Video render failed: {str(e)}"
            )
            
        # 5. Upload Video to Supabase Storage
        video_url = None
        try:
            supabase = get_supabase_client()
            file_name = f"{int(time.time())}_{payload.user_id}.mp4"
            
            with open(video_path, "rb") as vf:
                video_bytes = vf.read()
                
            supabase.storage.from_("videos").upload(
                path=file_name,
                file=video_bytes,
                file_options={"content-type": "video/mp4"}
            )
            
            video_url = supabase.storage.from_("videos").get_public_url(file_name)
        except Exception as e:
            logger.error("Failed to upload output video to storage", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Upload of generated video failed: {str(e)}"
            )
        finally:
            # Clean up temp video file if exists
            if 'video_path' in locals() and os.path.exists(video_path):
                try:
                    os.remove(video_path)
                except Exception:
                    pass
                    
        return {
            "status": "success",
            "video_url": video_url,
            "file_name": file_name,
            "pages_processed": len(pages)
        }
        
    finally:
        # Clean up all temporary files created during this request
        if local_pdf and os.path.exists(local_pdf):
            try:
                os.remove(local_pdf)
            except Exception:
                pass
        for page in pages_to_clean:
            if page.get("image_path") and os.path.exists(page["image_path"]):
                try:
                    os.remove(page["image_path"])
                except Exception:
                    pass
            if page.get("audio_path") and os.path.exists(page["audio_path"]):
                try:
                    os.remove(page["audio_path"])
                except Exception:
                    pass
