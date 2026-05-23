from pydantic import BaseModel
from typing import Optional, List

class GenerationRequest(BaseModel):
    user_id: str
    pdf_path: str
    voice_name: Optional[str] = "en-US-Neural2-F"
    pace: Optional[str] = "normal"
