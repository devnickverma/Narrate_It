import os
import time
import json
from fastapi import APIRouter, HTTPException, status, Request
from fastapi.responses import StreamingResponse
from backend.models.generate import GenerationRequest
from backend.services.pdf_service import download_pdf, split_pdf_to_pages
from backend.services.narration_service import generate_narration
from backend.services.tts_service import generate_audio
from backend.services.video_service import generate_video
from backend.services.supabase_client import get_supabase_client, get_authenticated_supabase_client
from backend.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/generate", tags=["generate"])

@router.post("/video")
async def generate_video_pipeline(request: Request, payload: GenerationRequest):
    logger.info(f"Triggering video generation pipeline for user: {payload.user_id} with PDF: {payload.pdf_path}")
    
    auth_header = request.headers.get("Authorization")
    jwt_token = None
    user_id = payload.user_id
    if auth_header and auth_header.startswith("Bearer "):
        jwt_token = auth_header.split(" ")[1]
        try:
            from backend.services.supabase_client import get_authenticated_supabase_client
            client = get_authenticated_supabase_client(jwt_token)
            response = client.auth.get_user()
            if response and response.user:
                user_id = response.user.id
                logger.info(f"[GENERATE] Authenticated user_id from JWT: {user_id}")
        except Exception as e:
            logger.error("Failed to extract authenticated user_id from JWT session in generation pipeline", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Authentication failed: {str(e)}"
            )

    async def progress_generator():
        # Phase 1: Uploading PDF (10%)
        # The PDF is already uploaded at this point, but we yield it immediately to initialize the progress bar.
        yield json.dumps({"phase": 1, "progress": 10, "message": "Phase 1: Uploading PDF"}) + "\n"
        
        # Phase 2: Extracting PDF pages (25%)
        yield json.dumps({"phase": 2, "progress": 25, "message": "Phase 2: Extracting PDF pages"}) + "\n"
        
        local_pdf = None
        pages = []
        try:
            local_pdf = download_pdf(payload.pdf_path, jwt_token)
            pages = split_pdf_to_pages(local_pdf)
        except Exception as e:
            logger.error("PDF download/extraction stage failed", exc_info=True)
            yield json.dumps({"status": "error", "message": f"PDF processing failed: {str(e)}"}) + "\n"
            return
            
        # Phase 3: Generating Gemini narration (45%)
        yield json.dumps({"phase": 3, "progress": 45, "message": "Phase 3: Generating Gemini narration"}) + "\n"
        
        try:
            for page in pages:
                pn = page["page_number"]
                script = generate_narration(
                    page_text=page["text"],
                    context=None,
                    user_id=user_id,
                    image_path=page["image_path"],
                    jwt_token=jwt_token
                )
                page["script"] = script
        except Exception as e:
            logger.error("Narration generation stage failed", exc_info=True)
            yield json.dumps({"status": "error", "message": f"Narration generation failed: {str(e)}"}) + "\n"
            cleanup_files(local_pdf, pages)
            return
            
        # Phase 4: Generating Deepgram audio (65%)
        yield json.dumps({"phase": 4, "progress": 65, "message": "Phase 4: Generating Deepgram audio"}) + "\n"
        
        narrations_list = []
        try:
            for page in pages:
                pn = page["page_number"]
                voice = payload.voice_name or "aura-asteria-en"
                speed = 1.0
                if payload.pace == "slow":
                    speed = 0.85
                elif payload.pace == "fast":
                    speed = 1.15
                
                audio_path = generate_audio(
                    text=page["script"],
                    user_id=user_id,
                    page=pn,
                    voice_model=voice,
                    speed=speed,
                    jwt_token=jwt_token
                )
                page["audio_path"] = audio_path
                
                narrations_list.append({
                    "page": pn,
                    "text": page["script"],
                    "image_path": page["image_path"],
                    "audio_path": audio_path
                })
                # Sleep briefly
                time.sleep(0.5)
        except Exception as e:
            logger.error("Audio generation stage failed", exc_info=True)
            yield json.dumps({"status": "error", "message": f"Audio generation failed: {str(e)}"}) + "\n"
            cleanup_files(local_pdf, pages)
            return
            
        # Phase 5: Rendering MP4 video (85%)
        yield json.dumps({"phase": 5, "progress": 85, "message": "Phase 5: Rendering MP4 video"}) + "\n"
        
        video_path = None
        try:
            video_path = generate_video(narrations_list, user_id)
        except Exception as e:
            logger.error("Video rendering stage failed", exc_info=True)
            yield json.dumps({"status": "error", "message": f"Video render failed: {str(e)}"}) + "\n"
            cleanup_files(local_pdf, pages)
            return
            
        # Phase 6: Uploading final video (100%)
        yield json.dumps({"phase": 6, "progress": 100, "message": "Phase 6: Uploading final video"}) + "\n"
        
        try:
            if jwt_token:
                supabase = get_authenticated_supabase_client(jwt_token)
            else:
                supabase = get_supabase_client()
            
            file_name = f"{int(time.time())}_{user_id}.mp4"
            logger.info(f"[VIDEO_UPLOAD] Authenticated storage upload started for file {file_name}")
            
            with open(video_path, "rb") as vf:
                video_bytes = vf.read()
                
            supabase.storage.from_("videos").upload(
                path=file_name,
                file=video_bytes,
                file_options={"content-type": "video/mp4"}
            )
            logger.info("[VIDEO_UPLOAD] Upload completed successfully")
            
            video_url = supabase.storage.from_("videos").get_public_url(file_name)
            logger.info(f"[VIDEO_UPLOAD] Public URL generated: {video_url}")
            
            yield json.dumps({
                "status": "success",
                "video_url": video_url,
                "file_name": file_name,
                "pages_processed": len(pages)
            }) + "\n"
        except Exception as e:
            logger.error("Video upload stage failed", exc_info=True)
            yield json.dumps({"status": "error", "message": f"Upload of generated video failed: {str(e)}"}) + "\n"
        finally:
            if video_path and os.path.exists(video_path):
                try:
                    os.remove(video_path)
                except Exception:
                    pass
            cleanup_files(local_pdf, pages)

    return StreamingResponse(progress_generator(), media_type="application/x-ndjson")

def cleanup_files(local_pdf, pages):
    if local_pdf and os.path.exists(local_pdf):
        try:
            os.remove(local_pdf)
        except Exception:
            pass
    for page in pages:
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
