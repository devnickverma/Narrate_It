import uuid
import tempfile
import os
import fitz  # PyMuPDF
from backend.services.supabase_client import get_supabase_client, get_authenticated_supabase_client
from typing import List, Dict, Any
from backend.utils.logger import get_logger

logger = get_logger(__name__)

def upload_pdf(file_bytes: bytes, user_id: str, jwt_token: str = None) -> str:
    """Uploads a PDF file to Supabase Storage and returns the storage path."""
    if jwt_token:
        logger.info(f"[UPLOAD] Authenticated upload started for user {user_id}")
        supabase = get_authenticated_supabase_client(jwt_token)
        logger.info("[UPLOAD] JWT attached successfully")
    else:
        logger.info(f"Starting PDF upload for user {user_id}")
        supabase = get_supabase_client()
    
    file_uuid = str(uuid.uuid4())
    storage_path = f"{user_id}/{file_uuid}.pdf"
    
    try:
        supabase.storage.from_("pdfs").upload(
            path=storage_path,
            file=file_bytes,
            file_options={"content-type": "application/pdf"}
        )
        if jwt_token:
            logger.info("[UPLOAD] Storage upload completed")
        else:
            logger.info(f"Successfully uploaded PDF to {storage_path}")
        
        logger.info(f"[UPLOAD] Final storage path: {storage_path}")
    except Exception as e:
        logger.error(f"Failed to upload PDF to path {storage_path}", exc_info=True)
        raise Exception(f"Failed to upload PDF: {str(e)}")
        
    return storage_path

def download_pdf(storage_path: str, jwt_token: str = None) -> str:
    """Downloads a PDF from Supabase Storage to a temporary file."""
    # Clean the storage path to prevent mismatch bugs (strip prepended bucket names or slashes)
    cleaned_path = storage_path
    if cleaned_path.startswith("pdfs/"):
        cleaned_path = cleaned_path[len("pdfs/"):]
    if cleaned_path.startswith("/"):
        cleaned_path = cleaned_path.lstrip("/")
    logger.info(f"[DOWNLOAD] Requested storage path: {storage_path}")
    
    if jwt_token:
        supabase = get_authenticated_supabase_client(jwt_token)
    else:
        supabase = get_supabase_client()
    
    try:
        response = supabase.storage.from_("pdfs").download(cleaned_path)
    except Exception as e:
        logger.error(f"Failed to download PDF from {cleaned_path}", exc_info=True)
        raise Exception(f"Failed to download PDF: {str(e)}")
        
    # Save to temp file
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    temp_file.write(response)
    temp_file.close()
    
    logger.info(f"Successfully downloaded PDF to temporary file {temp_file.name}")
    return temp_file.name

def split_pdf_to_pages(pdf_path: str) -> List[Dict[str, Any]]:
    """Splits a PDF into pages, extracts text, and generates image previews."""
    logger.info(f"Splitting PDF {pdf_path} into pages")
    pages_data = []
    doc = None
    try:
        doc = fitz.open(pdf_path)
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            
            # Extract text
            text = page.get_text().strip()
            
            # Generate image (PNG)
            pix = page.get_pixmap()
            
            # Save image to temp file
            img_fd, img_path = tempfile.mkstemp(suffix=".png")
            os.close(img_fd)
            pix.save(img_path)
            
            pages_data.append({
                "page_number": page_num + 1,
                "text": text,
                "image_path": img_path
            })
        logger.info(f"Successfully split PDF into {len(pages_data)} pages")
    except Exception as e:
        logger.error("Failed to process and split PDF", exc_info=True)
        raise Exception(f"Failed to process PDF: {str(e)}")
    finally:
        if doc is not None:
            doc.close()
            
    return pages_data
