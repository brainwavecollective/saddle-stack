from fastapi import HTTPException
from typing import Any, Optional, Dict

class BaseAPIException(HTTPException):
    """Base exception for API errors"""
    def __init__(
        self,
        status_code: int,
        detail: str,
        headers: Optional[Dict[str, Any]] = None
    ):
        super().__init__(status_code=status_code, detail=detail, headers=headers)

class TextProcessingError(BaseAPIException):
    """Raised when text processing fails"""
    def __init__(self, detail: str = "Failed to process text"):
        super().__init__(status_code=500, detail=detail)

class AudioGenerationError(BaseAPIException):
    """Raised when audio generation fails"""
    def __init__(self, detail: str = "Failed to generate audio"):
        super().__init__(status_code=500, detail=detail)

class AIServiceError(BaseAPIException):
    """Raised when AI service encounters an error"""
    def __init__(self, detail: str = "AI service error"):
        super().__init__(status_code=500, detail=detail)

class WebSocketError(BaseAPIException):
    """Raised when WebSocket operations fail"""
    def __init__(self, detail: str = "WebSocket error"):
        super().__init__(status_code=500, detail=detail)