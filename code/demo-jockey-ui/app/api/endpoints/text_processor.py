"""
Brain Wave Collective
https://brainwavecollective.ai
  Revolutionizing Video Creation with TwelveLabs Jockey and NVIDIA AI Workbench. 
  Jockbench is our submission to the Dell x NVIDIA HackAI Challenge
File: text_processor.py
Created: 2024
Authors: Thienthanh Trinh & Daniel Ritchie
Copyright (c) 2024 Brain Wave Collective
"""

# app/api/endpoints/text_procesor.py

from fastapi import APIRouter, HTTPException, Request, Query, WebSocket
from fastapi.websockets import WebSocketDisconnect
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from loguru import logger
import uuid
from datetime import datetime
from pathlib import Path
import asyncio
from sse_starlette.sse import EventSourceResponse
from app.services.websocket_manager import WebSocketManager
import time
from typing import Optional, Dict, Any
import json 

# Initialize the WebSocket manager
ws_manager = WebSocketManager()

router = APIRouter()

# Models
class InitResponse(BaseModel):
    thread_id: str
    status: str = "initialized"

class TextProcessRequest(BaseModel):
    text: str
    thread_id: str
    index_id: Optional[str] = None

class ProcessResponse(BaseModel):
    operation_id: str
    status: str
    timeline: Dict[str, str]
    stats: Optional[Dict[str, Any]]
    response: Dict[str, Any]

@router.get("/config/index-id")
async def get_default_index_id(request: Request):
    """Get the default index ID from settings"""
    settings = request.app.state.settings
    return {"index_id": settings.twelve_labs_index_id}
    
@router.post("/process/init", response_model=InitResponse)
async def initialize_process(request: Request):
    """Initialize a new processing thread and return its ID"""
    start_time = time.time()
    try:
        thread_id = await ws_manager.create_thread()
        return InitResponse(thread_id=thread_id)
    except Exception as e:
        logger.error(f"[{time.time() - start_time:.2f}s] Error initializing process: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/process", response_model=ProcessResponse)
async def process_text(request: TextProcessRequest, req: Request):
    """Process text for Jockey generation"""
    start_time = time.time()
    try:
        logger.info(f"[{start_time}] Processing text: {request.text}")
        logger.debug(f"Using index_id: {request.index_id}")
                
        # Get services
        logger.debug("Initializing services...")
        jockey_service = req.app.state.jockey_service
        settings = req.app.state.settings
        
        # Get index_id from request or fall back to settings
        index_id = request.index_id or settings.twelve_labs_index_id
        logger.debug(f"Resolved index_id: {index_id}")

        # Generate operation ID and setup
        operation_id = str(uuid.uuid4())
        logger.info(f"Generated operation_id: {operation_id}")
        
        # Initialize response with all required fields
        response = {
            "operation_id": operation_id,
            "status": "processing",
            "audio_urls": {},             
            "response": {},  
            "timeline": {
                "start_time": datetime.utcnow().isoformat(),
            },
            "stats": {}
        }
        
        # Start background tasks
        logger.debug("Starting background task for Jockey...")
        jockey_task = asyncio.create_task(
            handle_jockey_stream(
                jockey_service,
                request.text,
                request.thread_id,
                index_id=index_id
            )
        )
       
        await jockey_task  # Ensure Jockey task completes
        return ProcessResponse(**response)
        
    except Exception as e:
        logger.error(f"[{time.time() - start_time:.2f}s] Error processing text: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Clean up all resources
        try:
            await ws_manager.disconnect_from_jockey(request.thread_id)
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
                
@router.get("/stream")
async def stream_updates(request: Request, thread_id: str = Query(...)):
    """SSE endpoint for streaming updates"""

    def parse_nested_json(content: str, max_depth: int = 5) -> Any:
        """Recursively parse nested JSON strings"""
        logger.debug(f"Starting parse_nested_json with content: {content}")
        for depth in range(max_depth):
            if not isinstance(content, str):
                logger.debug(f"Content is not a string at depth {depth}: {content}")
                break
            try:
                parsed_content = json.loads(content)
                logger.debug(f"parse_nested_json depth {depth}: Successfully parsed content: {parsed_content}")
                content = parsed_content
            except json.JSONDecodeError as e:
                logger.debug(f"parse_nested_json depth {depth}: JSONDecodeError: {e}")
                break
        return content

    def prepare_display_message(message: Any) -> Optional[dict]:
        """Transform raw messages into display-ready format"""
        try:
            logger.debug(f"prepare_display_message: Received message: {message}")

            # If the message is a string, try to parse it as JSON
            if isinstance(message, str):
                logger.debug(f"Message is a string: {message}")
                if message.strip().lower() in ["values", "metadata"]:
                    logger.debug("Message is 'values' or 'metadata'; skipping.")
                    return None
                try:
                    message = json.loads(message)
                    logger.debug(f"Parsed string as JSON: {message}")
                except json.JSONDecodeError:
                    logger.debug("String is not valid JSON; treating as plain text.")
                    return {
                        "text": message,
                        "type": "system"
                    }

            # Now, message is expected to be a dict after parsing
            if isinstance(message, dict):
                logger.debug(f"Message is a dict: {message}")
                content = message.get('content')
                msg_type = message.get('type')
                msg_name = message.get('name')
                
                if not content:
                    logger.debug("No content found in message; skipping.")
                    return None

                # Handle instructor and planner messages directly
                if msg_type == 'human' and msg_name in ['instructor', 'planner']:
                    return {
                        "text": f"🎬\n\n{content}",
                        "type": msg_type,
                        "name": msg_name
                    }

                # Mask AI summary messages, make broad assumptions 
                if msg_type == 'ai':
                    logger.debug(f"Found AI message, obfusating: {content}")
                    return {
                        "text": "✨ AI processing complete.",
                        "type": msg_type,
                        "name": msg_name
                    }

                # Content might be a nested JSON string; attempt to parse it
                if isinstance(content, str):
                    content = parse_nested_json(content)
                    logger.debug(f"After parse_nested_json, content: {content}")

                # Handle video messages
                if isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict) and item.get('type') == 'tool_call':
                            if item.get('name') == 'combine-clips':
                                logger.debug("Found combine-clips tool call")
                                return {
                                    "data": json.dumps([item]),
                                    "type": "system",
                                    "name": "video-ready",
                                    "text": "🎥 Your video is ready!" 
                                }
                            elif item.get('name') == 'simple-video-search':
                                # Optional status message for searches
                                return {
                                    "text": "🔍 Analyzing videos to find the perfect clip...",
                                    "type": "system",
                                    "name": "status"
                                }
                
                # Filter out all other messages
                return None

            logger.debug(f"Message is of unhandled type {type(message)}: {message}")
            return None

        except Exception as e:
            logger.error(f"Error in prepare_display_message: {e}", exc_info=True)
            return None

    async def event_generator():
        if not thread_id:
            logger.error("No thread_id provided; exiting event_generator.")
            # Yield an error message to the client
            yield f"event: error\ndata: No thread_id provided\n\n"
            return

        try:
            queue = await ws_manager.ensure_jockey_queue(thread_id)
            logger.debug(f"Obtained queue for thread_id {thread_id}")
        except Exception as e:
            logger.error(f"Failed to get queue for thread_id {thread_id}: {e}", exc_info=True)
            # Yield an error message to the client
            yield f"event: error\ndata: Failed to get queue for thread_id\n\n"
            return

        try:
            while True:
                if await request.is_disconnected():
                    logger.info(f"Client disconnected from thread {thread_id}")
                    break

                try:
                    message = await asyncio.wait_for(queue.get(), timeout=1.0)
                    logger.debug(f"Received message from queue: {message}")

                    # Transform to display format
                    display_message = prepare_display_message(message)
                    if display_message:
                        logger.debug(f"[SSE] Sending display message: {display_message}")
                        yield f"event: message\ndata: {json.dumps(display_message)}\n\n"
                    else:
                        logger.debug("prepare_display_message returned None; message not sent.")
                except asyncio.TimeoutError:
                    # Send ping event to keep connection alive
                    yield f"event: ping\ndata: \n\n"
                except Exception as e:
                    logger.error(f"Error in event_generator loop: {e}", exc_info=True)
        finally:
            await ws_manager.disconnect_from_jockey(thread_id)
            logger.debug(f"Disconnected from Jockey for thread_id {thread_id}")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )
        
async def handle_jockey_stream(jockey_service, text: str, thread_id: str, index_id: Optional[str] = None):
    """Handle Jockey streaming in background"""
    start_time = time.time()
    try:
        logger.debug(f"Starting Jockey stream processing for thread {thread_id}")
        if not index_id:
            error_msg = "Index ID is required for processing but was not provided."
            logger.error(f"[{time.time() - start_time:.2f}s] {error_msg}")
            await ws_manager.send_jockey_update(thread_id=thread_id, message={"error": error_msg})
            return
            
        logger.debug(f"Processing with index_id: {index_id}")
        
        # Add logging for the actual stream processing
        try:
            async for response in jockey_service.stream_processing(
                text=text,
                index_id=index_id, 
                thread_id=thread_id
            ):
                logger.debug(f"Received Jockey response type: {type(response)}")
                logger.debug(f"Response dict: {response.dict() if hasattr(response, 'dict') else str(response)}")
                logger.debug(f"Response content type: {type(response.content) if hasattr(response, 'content') else 'no content'}")
                logger.debug(f"Raw response: {response}")
                
                
                if hasattr(response, 'content'):
                    await ws_manager.send_jockey_update(thread_id=thread_id, message=response.content)
                else:
                    logger.warning(f"Received unexpected response format: {response}")
                    
        except Exception as stream_error:
            logger.error(f"Error during Jockey stream processing: {stream_error}")
            await ws_manager.send_jockey_update(
                thread_id=thread_id, 
                message={"error": f"Stream processing error: {str(stream_error)}"}
            )
            
        logger.debug(f"Completed Jockey stream processing for thread {thread_id}")
    except Exception as e:
        error_msg = f"Error in Jockey processing: {str(e)}"
        logger.error(f"[{time.time() - start_time:.2f}s] {error_msg}")
        await ws_manager.send_jockey_update(thread_id=thread_id, message={"error": error_msg})
      