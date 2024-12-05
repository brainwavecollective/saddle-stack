# app/models/schemas/text_processor.py

from pydantic import BaseModel
from typing import Dict, Optional

class TextProcessRequest(BaseModel):
    text: str

class ProcessResponse(BaseModel):
    operation_id: str
    status: str
    audio_urls: Dict[str, str]
    response: Optional[Dict] = None
    timeline: Optional[Dict] = None
    stats: Optional[Dict] = None
  