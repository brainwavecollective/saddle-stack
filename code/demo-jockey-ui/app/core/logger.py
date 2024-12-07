"""
Brain Wave Collective
https://brainwavecollective.ai
  Revolutionizing Video Creation with TwelveLabs Jockey and NVIDIA AI Workbench. 
  Saddle Stack (AKA Jockbench) is our submission to the Dell x NVIDIA HackAI Challenge
File: logger.py
Created: 2024
Authors: Thienthanh Trinh & Daniel Ritchie
Copyright (c) 2024 Brain Wave Collective
"""

import sys
from pathlib import Path
from loguru import logger
from app.core.config import get_settings

def setup_logging():
    settings = get_settings()
    
    Path(settings.LOGS_DIR).mkdir(parents=True, exist_ok=True)
    logger.remove()
    
    logger.add(
        f"{settings.LOGS_DIR}/app.log",
        rotation="1 day",  # Default value
        retention="10 days",  # Default value
        level=settings.LOG_LEVEL,
        format=settings.LOG_FORMAT,
        backtrace=True,
        diagnose=True
    )
    
    logger.add(
        f"{settings.LOGS_DIR}/error.log",
        rotation="1 day",
        retention="10 days",
        level="ERROR",
        format=settings.LOG_FORMAT,
        backtrace=True,
        diagnose=True
    )
    
    if settings.DEBUG:
        logger.add(
            sys.stderr,
            level="DEBUG" if settings.DEBUG else "INFO",
            format=settings.LOG_FORMAT,
            colorize=True
        )
    return logger