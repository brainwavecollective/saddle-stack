"""
Brain Wave Collective
https://brainwavecollective.ai
  Revolutionizing Video Creation with TwelveLabs Jockey and NVIDIA AI Workbench. 
  Jockbench is our submission to the Dell x NVIDIA HackAI Challenge
File: jockey.py
Created: 2024
Authors: Thienthanh Trinh & Daniel Ritchie
Copyright (c) 2024 Brain Wave Collective
"""

from fastapi import APIRouter, Request, HTTPException, WebSocket, WebSocketDisconnect
from app.schemas.jockey import JockeyRequest, JockeyResponse, AssistantInfo
from loguru import logger
from typing import List
import json

router = APIRouter()

@router.get("/assistants", response_model=List[AssistantInfo])
async def list_assistants(request: Request):
    """List available Jockey assistants"""
    try:
        jockey_service = request.app.state.jockey_service
        return await jockey_service.list_assistants()
    except Exception as e:
        logger.error(f"Error listing assistants: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/thread")
async def create_thread(request: Request):
    """Create a new processing thread"""
    try:
        jockey_service = request.app.state.jockey_service
        thread_id = await jockey_service.create_thread()
        return {"thread_id": thread_id}
    except Exception as e:
        logger.error(f"Error creating thread: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for streaming Jockey responses"""
    await websocket.accept()
    try:
        while True:
            # Receive and parse the message
            data = await websocket.receive_text()
            try:
                request = JockeyRequest.parse_raw(data)

                if not request.index_id:
                    logger.error("Missing Index ID in request")
                    await websocket.send_text(
                        JockeyResponse(
                            operation_id="error",
                            type="error",
                            status="error",
                            content="Index ID is required to proceed."
                        ).json()
                    )
                    return

                
            except Exception as e:
                logger.error(f"Error parsing request: {e}")
                await websocket.send_text(
                    JockeyResponse(
                        operation_id="error",
                        type="error",
                        status="error",
                        content=f"Invalid request format: {str(e)}"
                    ).json()
                )
                continue
            
            # Get the Jockey service from app state
            jockey_service = websocket.app.state.jockey_service
            
            try:
                # Process the request and stream responses
                async for response in jockey_service.stream_processing(
                    text=request.text,
                    index_id=request.index_id,
                    thread_id=request.thread_id,
                    assistant_id=request.assistant_id,
                    stream_mode=request.stream_mode  # Add stream_mode parameter
                ):
                    # Ensure response is properly formatted
                    if not isinstance(response, JockeyResponse):
                        response = JockeyResponse(
                            type="message",
                            content=str(response),
                            status="streaming",
                            operation_id=request.operation_id if hasattr(request, 'operation_id') else "unknown"
                        )
                    
                    try:
                        await websocket.send_text(response.json())
                    except Exception as e:
                        logger.error(f"Error sending response: {e}")
                        await websocket.send_text(
                            JockeyResponse(
                                operation_id="error",
                                type="error",
                                status="error",
                                content=f"Error sending response: {str(e)}"
                            ).json()
                        )
                        break
                    
            except Exception as e:
                logger.error(f"Error processing request: {e}")
                await websocket.send_text(
                    JockeyResponse(
                        operation_id="error",
                        type="error",
                        status="error",
                        content=f"Error processing request: {str(e)}"
                    ).json()
                )
                
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        try:
            await websocket.send_text(
                JockeyResponse(
                    operation_id="error",
                    type="error",
                    status="error",
                    content=f"WebSocket error: {str(e)}"
                ).json()
            )
        except:
            logger.error("Failed to send error message to client")
    finally:
        try:
            await websocket.close()
        except:
            pass