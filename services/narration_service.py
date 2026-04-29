from google import genai
from services.key_service import get_api_keys
from utils.logger import get_logger
from PIL import Image
import re

logger = get_logger(__name__)

def detect_content_type(page_text: str, image) -> str:
    """Heuristic to detect the type of content on a page."""
    text = page_text.strip() if page_text else ""
    text_len = len(text)
    
    # 1. VISUAL: Empty or very short text AND image exists
    if text_len < 150 and image is not None:
        return "visual"
        
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    
    if not lines:
        return "visual" if image is not None else "text"
        
    paragraphs = [p for p in text.split('\n\n') if p.strip()]
    long_paragraphs_count = sum(1 for p in paragraphs if len(p) > 200)
    
    # 2. TEXT (Academic/Structured)
    text_lower = text.lower()
    academic_keywords = ["abstract", "introduction", "method", "conclusion"]
    has_academic_keywords = any(kw in text_lower for kw in academic_keywords)
    
    avg_line_length = text_len / len(lines) if lines else 0
    
    if has_academic_keywords or long_paragraphs_count > 0 or avg_line_length > 80:
        return "text"
        
    # 3. PRESENTATION
    bullet_markers = ('•', '-', '*', '1.', '2.')
    bullet_count = sum(1 for line in lines if line.startswith(bullet_markers))
    
    if bullet_count >= 3 and avg_line_length < 60 and long_paragraphs_count == 0:
        return "presentation"
        
    # Safety fallback
    return "text"

def generate_narration(page_text: str, context: list[str] | None, user_id: str, image_path: str = None) -> str:
    """Generates a narration script for a given PDF page text and image using Gemini."""
    logger.info(f"Generating narration for user {user_id}")
    
    keys = get_api_keys(user_id)
    gemini_api_key = keys.get("gemini_key")
    
    if not gemini_api_key:
        logger.error("Gemini API key is missing")
        raise ValueError("Gemini API key is missing. Please configure it in your settings.")
        
    try:
        client = genai.Client(api_key=gemini_api_key)
        
        logger.info("Generating concise, professional narration")
        
        # Load image if provided
        image = None
        if image_path:
            try:
                image = Image.open(image_path)
            except Exception as e:
                logger.warning(f"Failed to load image at {image_path}, falling back to text-only mode: {e}")
        
        # Detect content type
        content_type = detect_content_type(page_text, image)
        text_length = len(page_text) if page_text else 0
        logger.info(f"Detected content type: {content_type} | text_length={text_length}")
        
        common_instructions = (
            "CRITICAL INSTRUCTIONS for Voiceover Script:\n"
            "- Output must feel like a documentary narration or video voiceover. Not a chatbot.\n"
            "- Limit output to 4-8 sentences per page.\n"
            "- DO NOT use conversational filler like 'Hello', 'Today we are going to', 'Let's break down', 'Do you have any questions?', or 'Would you like me to...'\n"
            "- Avoid long paragraphs. Keep sentences clear, direct, and medium-length.\n"
            "- Do not over-explain, add extra examples, or repeat yourself.\n"
            "- Focus ONLY on key ideas, main actions, and essential context.\n"
        )
        
        if content_type == "visual":
            base_prompt = (
                "You are an expert narrator for manga/comics.\n\n"
                f"{common_instructions}\n"
                "Specific Rules:\n"
                "* Use a storytelling tone.\n"
                "* Describe the main scene only.\n"
                "* Include key dialogue if visible.\n"
                "* Avoid excessive detail."
            )
        elif content_type == "presentation":
            base_prompt = (
                "You are presenting slides to an audience.\n\n"
                f"{common_instructions}\n"
                "Specific Rules:\n"
                "* Keep it concise and structured.\n"
                "* Highlight the top 3-5 key points.\n"
                "* Avoid long explanations."
            )
        else:
            base_prompt = (
                "You are a professional voiceover narrator.\n\n"
                f"{common_instructions}\n"
                "Specific Rules:\n"
                "* Provide a clear and structured explanation.\n"
                "* Use a formal but simple tone.\n"
                "* Summarize the content, do not lecture.\n"
                "* Example tone: 'This section explains...', 'The concept focuses on...'"
            )
            
        prompt_text = base_prompt
        
        if context and len(context) > 0:
            prompt_text += "\n\nPrevious context:\n"
            for summary in context:
                prompt_text += f"- {summary}\n"
                
        contents = [prompt_text]
        
        if page_text and page_text.strip():
            contents.append(f"Extracted text (for reference): {page_text}")
            
        if image is not None:
            contents.append(image)
                
        try:
            logger.info("Using Gemini model: gemini-flash-lite-latest")
            response = client.models.generate_content(
                model="gemini-flash-lite-latest",
                contents=contents
            )
        except Exception as primary_e:
            logger.warning("Primary model failed, switching to gemini-flash-latest")
            response = client.models.generate_content(
                model="gemini-flash-latest",
                contents=contents
            )
        
        if not response.text:
            raise Exception("Received empty response from Gemini.")
            
        cleaned_text = response.text.strip()
        if not cleaned_text:
            raise Exception("Received blank response from Gemini after cleaning.")
            
        # Hard constraint: Trim if output is too long (> 8 sentences)
        sentences = re.split(r'(?<=[.!?])\s+', cleaned_text)
        if len(sentences) > 8:
            cleaned_text = " ".join(sentences[:8])
            logger.info("Trimmed response to 8 sentences to enforce length limit.")
            
        logger.info("Successfully generated narration script.")
        return cleaned_text
    except Exception as e:
        logger.error("Failed to generate narration from Gemini API", exc_info=True)
        raise Exception("Failed to generate narration. Please check logs for details.")
