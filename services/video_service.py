import os
import tempfile
from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips, TextClip, CompositeVideoClip

from utils.logger import get_logger

logger = get_logger(__name__)

def generate_video(narrations: list, user_id: str) -> str:
    """Combines images and audio narrations into a final video."""
    logger.info("Generating final video")
    
    try:
        clips = []
        for narration in narrations:
            if "image_path" not in narration or "audio_path" not in narration:
                logger.error(f"Missing image or audio for page {narration.get('page')}")
                continue
                
            image_path = narration["image_path"]
            audio_path = narration["audio_path"]
            
            # Load audio to get its duration
            audio_clip = AudioFileClip(audio_path)
            
            # Create an image clip matching the duration of the audio
            image_clip = ImageClip(image_path).set_duration(audio_clip.duration)
            
            # --- Try Adding Subtitles ---
            try:
                subtitle_text = narration.get("text", "")
                if subtitle_text:
                    # Truncate text just in case to prevent massive overflow, or show key concepts
                    short_text = subtitle_text[:120] + "..." if len(subtitle_text) > 120 else subtitle_text
                    txt_clip = TextClip(
                        txt=short_text,
                        font="DejaVu-Sans",
                        fontsize=30,
                        color='white',
                        stroke_color='black',
                        stroke_width=2,
                        method='label'
                    )
                    txt_clip = txt_clip.set_position(('center', 'bottom')).set_duration(audio_clip.duration)
                    image_clip = CompositeVideoClip([image_clip, txt_clip])
            except Exception as sub_e:
                logger.warning(f"Failed to add subtitle for page {narration.get('page')}, skipping: {sub_e}")
                
            image_clip = image_clip.set_audio(audio_clip)
            
            # --- Try Adding Transitions ---
            try:
                if len(clips) > 0:
                    image_clip = image_clip.crossfadein(0.5)
            except Exception as fade_e:
                logger.warning(f"Failed to add crossfade for page {narration.get('page')}, skipping: {fade_e}")
            
            clips.append(image_clip)
            
        if not clips:
            raise ValueError("No valid clips were generated. Make sure pages have audio and images.")
            
        # Concatenate all clips sequentially
        final_video = concatenate_videoclips(clips, method="compose")
        
        # Save to temp file
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
        temp_file.close() # Close to write
        
        # Write video file
        final_video.write_videofile(
            temp_file.name, 
            fps=24, 
            codec="libx264", 
            audio_codec="aac"
        )
        
        # Clean up clips to free memory
        for clip in clips:
            clip.close()
        final_video.close()
            
        logger.info(f"Successfully generated video at {temp_file.name}")
        return temp_file.name
        
    except Exception as e:
        logger.error("Failed to generate final video", exc_info=True)
        raise Exception(f"Failed to generate final video: {str(e)}")
