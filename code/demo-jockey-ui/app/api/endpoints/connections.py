"""
Brain Wave Collective
https://brainwavecollective.ai
  Revolutionizing Video Creation with TwelveLabs Jockey and NVIDIA AI Workbench. 
  Jockbench is our submission to the Dell x NVIDIA HackAI Challenge
File: connections.py
Created: 2024
Authors: Thienthanh Trinh & Daniel Ritchie
Copyright (c) 2024 Brain Wave Collective
"""

# app/api/endpoints/connections.py
# Handles WebSocket connections and Server-Sent Events (SSE) for the application
from fastapi import WebSocket, APIRouter, Request
from fastapi.responses import StreamingResponse
from loguru import logger
from datetime import datetime
from typing import List, Dict, Any, AsyncGenerator
from fastapi.websockets import WebSocketDisconnect
import json
import asyncio

router = APIRouter()

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.active_threads: Dict[str, List[asyncio.Queue]] = {}
        self.service_routes = {
            "jockey": self.process_jockey
        }

        logger.info("ConnectionManager initialized")
        
    async def connect(self, websocket: WebSocket):
        """Accept and store new WebSocket connection"""
        try:
            await websocket.accept()
            self.active_connections.append(websocket)
            logger.info(f"New WebSocket connection. Total connections: {len(self.active_connections)}")
        except Exception as e:
            logger.error(f"Error accepting WebSocket connection: {e}")
            raise
            
    async def disconnect(self, websocket: WebSocket):
        """Remove WebSocket connection"""
        try:
            if websocket in self.active_connections:
                self.active_connections.remove(websocket)
                logger.info(f"WebSocket disconnected. Remaining connections: {len(self.active_connections)}")
        except Exception as e:
            logger.error(f"Error during WebSocket disconnect: {e}")

    def register_thread_queue(self, thread_id: str) -> asyncio.Queue:
        """Register a new queue for SSE updates"""
        if thread_id not in self.active_threads:
            self.active_threads[thread_id] = []
        queue = asyncio.Queue()
        self.active_threads[thread_id].append(queue)
        logger.info(f"New SSE queue registered for thread {thread_id}")
        return queue
        
    def remove_thread_queue(self, thread_id: str, queue: asyncio.Queue):
        """Remove a queue when SSE connection closes"""
        if thread_id in self.active_threads:
            if queue in self.active_threads[thread_id]:
                self.active_threads[thread_id].remove(queue)
                logger.info(f"SSE queue removed for thread {thread_id}")
            if not self.active_threads[thread_id]:
                del self.active_threads[thread_id]
                logger.info(f"Thread {thread_id} removed - no active queues")
                
    async def broadcast_to_thread(self, thread_id: str, message: Dict[str, Any]):
        """Broadcast message to all SSE connections for a thread"""
        if thread_id in self.active_threads:
            for queue in self.active_threads[thread_id]:
                await queue.put(message)
                logger.debug(f"Message broadcast to thread {thread_id}: {message}")

    async def process_jockey(self, websocket: WebSocket, data: Dict[str, Any]):
        """Process Jockey messages and stream responses"""
        try:
            jockey_service = websocket.app.state.jockey_service
            async for response in jockey_service.stream_response(
                text=data["text"],
                thread_id=data.get("thread_id"),
                assistant_id=data.get("assistant_id")
            ):
                await websocket.send_json(response)

        except Exception as e:
            logger.error(f"Error processing Jockey message: {e}")
            await websocket.send_json({
                "type": "error",
                "timestamp": datetime.utcnow().isoformat(),
                "error": str(e)
            })

connection_manager = ConnectionManager()

async def event_generator(request: Request, thread_id: str) -> AsyncGenerator[str, None]:
    """Generate SSE events for a thread"""
    queue = connection_manager.register_thread_queue(thread_id)
    
    try:
        while True:
            if await request.is_disconnected():
                break
                
            try:
                message = await asyncio.wait_for(queue.get(), timeout=30)
                yield f"data: {json.dumps(message)}\n\n"
            except asyncio.TimeoutError:
                yield ": keep-alive\n\n"
                
    except Exception as e:
        logger.error(f"Error in SSE stream: {e}")
    finally:
        connection_manager.remove_thread_queue(thread_id, queue)

@router.get("/stream")
async def stream_endpoint(request: Request, thread_id: str):
    """SSE endpoint for streaming updates"""
    return StreamingResponse(
        event_generator(request, thread_id),
        media_type="text/event-stream"
    )

@router.websocket("/ws/{service}")
async def websocket_endpoint(websocket: WebSocket, service: str):
    """Handle WebSocket connections for different services"""
    try:
        await connection_manager.connect(websocket)
        
        while True:
            try:
                data = await websocket.receive_json()

                processor = connection_manager.service_routes.get(service)
                if processor:
                    await processor(websocket, data)
                else:
                    raise ValueError(f"Unknown service: {service}")
                    
            except WebSocketDisconnect:
                logger.info("Client disconnected normally")
                break
                
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON received: {e}")
                await websocket.send_json({
                    "type": "error",
                    "error": "Invalid JSON format"
                })
                
    except Exception as e:
        logger.error(f"Error in WebSocket handler: {str(e)}")
        
    finally:
        await connection_manager.disconnect(websocket)
        logger.info("WebSocket connection cleaned up")