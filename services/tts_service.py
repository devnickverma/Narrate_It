import os
import tempfile
from deepgram import DeepgramClient
from services.key_service import get_api_keys
from utils.logger import get_logger

logger = get_logger(__name__)

def generate_audio(text: str, user_id: str, page: int, voice_model: str = "aura-asteria-en", speed: float = 1.0) -> str:
    """Generates audio for narration text using Deepgram."""
    logger.info(f"Generating audio for page {page} with voice {voice_model} and speed {speed}")
    
    keys = get_api_keys(user_id)
    deepgram_key = keys.get("deepgram_key")
    
    if not deepgram_key:
        logger.error("Deepgram API key is missing")
        raise ValueError("Deepgram API key is missing. Please configure it in your settings.")
        
    try:
        # Initialize Deepgram client
        deepgram = DeepgramClient(api_key=deepgram_key)
        
        # Save to temp file
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        temp_file.close() # Close so we can write to it cleanly below
        
        # Call the API
        try:
            kwargs = {"text": text, "model": voice_model}
            if speed != 1.0:
                kwargs["speed"] = speed
                
            response = deepgram.speak.v1.audio.generate(**kwargs)
            
            with open(temp_file.name, "wb") as audio_file:
                for chunk in response:
                    audio_file.write(chunk)
                    
        except Exception as e:
            if speed != 1.0:
                logger.warning("Deepgram failed with speed parameter, falling back to default speed.")
                # Fallback without speed
                response = deepgram.speak.v1.audio.generate(text=text, model=voice_model)
                with open(temp_file.name, "wb") as audio_file:
                    for chunk in response:
                        audio_file.write(chunk)
            else:
                # If speed was 1.0 and it failed, re-raise because it's a real error
                raise e
            
        logger.info(f"Successfully generated audio for page {page} at {temp_file.name}")
        return temp_file.name
        
    except Exception as e:
        logger.error(f"Failed to generate audio using Deepgram for page {page}", exc_info=True)
        raise Exception(f"Failed to generate audio: {str(e)}")
