"""
Brain Wave Collective
https://brainwavecollective.ai
  Revolutionizing Video Creation with TwelveLabs Jockey and NVIDIA AI Workbench. 
  Saddle Stack (AKA Jockbench) is our submission to the Dell x NVIDIA HackAI Challenge
File: video.py
Created: 2024
Authors: Thienthanh Trinh & Daniel Ritchie
Copyright (c) 2024 Brain Wave Collective
"""

# app/api/endpoints/video.py
from fastapi import APIRouter, HTTPException, Request, Response
import aiohttp
from loguru import logger
from app.core.config import get_settings 

router = APIRouter()
settings = get_settings()  

@router.get("/video/{index_id}/{filename}")
async def get_video(request: Request, index_id: str, filename: str):
    """Simple video proxy - no streaming, no ranges, just works"""
    try:
        url = f"{settings.jockey_static_url}/{index_id}/{filename}"
        logger.info(f"Fetching video from: {url}")
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    logger.error(f"Upstream server returned {response.status}")
                    raise HTTPException(
                        status_code=response.status, 
                        detail="Failed to fetch video"
                    )
                    
                content = await response.read()
                logger.info(f"Successfully fetched video: {len(content)} bytes")
                
                return Response(
                    content=content,
                    media_type='video/mp4'
                )
                
    except Exception as e:
        logger.error(f"Error proxying video: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))