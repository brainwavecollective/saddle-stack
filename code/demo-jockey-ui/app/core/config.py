"""
Brain Wave Collective
https://brainwavecollective.ai
  Revolutionizing Video Creation with TwelveLabs Jockey and NVIDIA AI Workbench. 
  Saddle Stack (AKA Jockbench) is our submission to the Dell x NVIDIA HackAI Challenge
File: config.py
Created: 2024
Authors: Thienthanh Trinh & Daniel Ritchie
Copyright (c) 2024 Brain Wave Collective
"""

from pydantic_settings import BaseSettings
from typing import Optional
from pathlib import Path
from functools import lru_cache

class Settings(BaseSettings):
    """
    Single source of truth for application configuration.
    All environment variables and configuration should be defined here.
    """
    # Application Info
    APP_NAME: str = "Jockey Frontend Demo"
    VERSION: str = "1.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"
    
    # Server Settings
    HOST: str = "0.0.0.0"
    PORT: int = 9000
    API_V1_PREFIX: str = "/api/v1"
    
    # Audio Settings
    AUDIO_SAMPLE_RATE: int = 44100
    AUDIO_CHANNELS: int = 1
    AUDIO_SAMPLE_WIDTH: int = 2   
    
    # Security
    CORS_ORIGINS: list = [
        "http://localhost:5173",
        "http://localhost:9000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:9000",
    ]

    # Necessary for ref but not currently used (could be)
    SERVER_IP: Optional[str] = None
    
    # External API Keys
    WEAVE_API_KEY: Optional[str] = None
    
    # Jockey Settings
    JOCKEY_API_URL: Optional[str] = None
    JOCKEY_API_KEY: Optional[str] = None
    JOCKEY_STATIC_URL: Optional[str] = None
    
    # Twelve Labs settings
    TWELVE_LABS_INDEX_ID: Optional[str] = None 
    
    # Audio Settings
    AUDIO_SAMPLE_RATE: int = 44100
    AUDIO_CHANNELS: int = 1
    AUDIO_SAMPLE_WIDTH: int = 2
    
    # Paths
    BASE_DIR: Path = Path(__file__).parent.parent.parent
    STATIC_DIR: Path = BASE_DIR / "app" / "static"
    ASSETS_DIR: Path = STATIC_DIR / "assets"
    AUDIO_DIR: Path = ASSETS_DIR / "audio"
    VIDEO_DIR: Path = ASSETS_DIR / "video"
    LOGS_DIR: Path = BASE_DIR / "logs"
    
    UPLOADS_AUDIO_PATH: Path = BASE_DIR / "uploads" / "audio"
    UPLOADS_VIDEO_PATH: Path = BASE_DIR / "uploads" / "video"
    LOG_PATH: Path = LOGS_DIR
    
    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
    
    static_audio_path: str = "app/static/assets/audio"
    
    class Config:
        env_file = ".env"
        case_sensitive = False

    # Lowercase property aliases
    @property
    def weave_api_key(self) -> Optional[str]:
        return self.WEAVE_API_KEY
        
    @property
    def uploads_audio_path(self) -> Path:
        return self.UPLOADS_AUDIO_PATH
        
    @property
    def uploads_video_path(self) -> Path:
        return self.UPLOADS_VIDEO_PATH
        
    @property
    def log_path(self) -> Path:
        return self.LOG_PATH

    @property
    def twelve_labs_index_id(self) -> Optional[str]:
        return self.TWELVE_LABS_INDEX_ID
        
    @property
    def jockey_api_url(self) -> Optional[str]:
        return self.JOCKEY_API_URL

    @property
    def jockey_static_url(self) -> Optional[str]:
        return self.JOCKEY_STATIC_URL
        
    @property
    def jockey_api_key(self) -> Optional[str]:
        return self.JOCKEY_API_KEY

    @property
    def jockey_static_url(self) -> Optional[str]:
        return self.JOCKEY_STATIC_URL
        
    @property
    def sample_rate(self) -> int:
        return self.AUDIO_SAMPLE_RATE
        
    @property
    def channels(self) -> int:
        return self.AUDIO_CHANNELS
        
    @property
    def sample_width(self) -> int:
        return self.AUDIO_SAMPLE_WIDTH
        

    def get_ws_url(self, endpoint: str) -> str:
        """Generate WebSocket URL based on environment"""
        protocol = "wss" if self.ENVIRONMENT == "production" else "ws"
        return f"{protocol}://{self.HOST}:{self.PORT}{endpoint}"
    
    @property
    def static_urls(self):
        """URL paths for static assets"""
        return {
            "audio": "/static/assets/audio",
            "video": "/static/assets/video",
            "images": "/static/assets/images"
        }

    def create_directories(self):
        """Ensure all required directories exist"""
        for directory in [self.AUDIO_DIR, self.VIDEO_DIR, self.LOGS_DIR]:
            directory.mkdir(parents=True, exist_ok=True)

@lru_cache
def get_settings() -> Settings:
    """Cached settings instance"""
    settings = Settings()
    settings.create_directories()
    return settings