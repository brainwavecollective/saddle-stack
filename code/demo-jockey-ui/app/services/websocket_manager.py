"""
Brain Wave Collective
https://brainwavecollective.ai
  Revolutionizing Video Creation with TwelveLabs Jockey and NVIDIA AI Workbench. 
  Saddle Stack (AKA Jockbench) is our submission to the Dell x NVIDIA HackAI Challenge
File: websocket_manager.py
Created: 2024
Authors: Thienthanh Trinh & Daniel Ritchie
Copyright (c) 2024 Brain Wave Collective
"""

from fastapi import WebSocket
from typing import Dict, Optional, Any, AsyncGenerator
import asyncio
from loguru import logger
from enum import Enum
from dataclasses import dataclass
import uuid

class WebSocketType(Enum):
    JOCKEY = "jockey"
    STATUS = "status"

class ConnectionState(Enum):
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"

@dataclass
class Connection:
    websocket: WebSocket
    state: ConnectionState
    queue: asyncio.Queue
    type: WebSocketType

class WebSocketManager:    
    def __init__(self):
        self._connections: Dict[str, Dict[WebSocketType, Connection]] = {}
        self._background_tasks: Dict[str, asyncio.Task] = {}
        self._jockey_queues: Dict[str, asyncio.Queue] = {}
        logger.info("WebSocket manager initialized")

    async def create_thread(self) -> str:
        """Create a new thread and initialize its queues"""
        thread_id = str(uuid.uuid4())
        await self.ensure_jockey_queue(thread_id)
        logger.debug(f"Created new thread: {thread_id}")
        return thread_id

    async def connect(self, thread_id: str, websocket: WebSocket, type: WebSocketType) -> Connection:
        """Establish a new WebSocket connection"""
        try:
            await websocket.accept()

            if thread_id not in self._connections:
                self._connections[thread_id] = {}

            connection = Connection(
                websocket=websocket,
                state=ConnectionState.CONNECTED,
                queue=asyncio.Queue(),
                type=type
            )

            self._connections[thread_id][type] = connection

            logger.info(f"New {type.value} connection established for thread {thread_id}")
            return connection

        except Exception as e:
            logger.error(f"Error establishing {type.value} connection: {e}")
            raise

    async def disconnect(self, thread_id: str, type: WebSocketType):
        """Close a specific connection"""
        try:
            if connection := self._get_connection(thread_id, type):
                connection.state = ConnectionState.DISCONNECTED
                try:
                    if connection.websocket.client_state.CONNECTED:
                        await connection.websocket.close()
                except Exception as e:
                    logger.warning(f"Error closing websocket: {e}")

                if task := self._background_tasks.get(thread_id):
                    task.cancel()
                    del self._background_tasks[thread_id]

                del self._connections[thread_id][type]
                if not self._connections[thread_id]:
                    del self._connections[thread_id]

                logger.info(f"Disconnected {type.value} for thread {thread_id}")

        except Exception as e:
            logger.error(f"Error disconnecting {type.value}: {e}")
            
    def _get_connection(self, thread_id: str, type: WebSocketType) -> Optional[Connection]:
        """Get connection if it exists"""
        return self._connections.get(thread_id, {}).get(type)

    # Jockey-specific methods
    async def ensure_jockey_queue(self, thread_id: str) -> asyncio.Queue:
        """Ensure Jockey queue exists for thread"""
        if thread_id not in self._jockey_queues:
            self._jockey_queues[thread_id] = asyncio.Queue()
            logger.debug(f"Created new Jockey queue for thread {thread_id}")
        return self._jockey_queues[thread_id]

    async def send_jockey_update(self, thread_id: str, message: Any):
        """Send update to Jockey queue"""
        if queue := self._jockey_queues.get(thread_id):
            logger.debug(f"[WebSocket] Sending Jockey message: {message}") 
            await queue.put(message)
            logger.debug(f"Sent Jockey update for thread {thread_id}")
        else:
            logger.warning(f"No Jockey queue found for thread {thread_id}")

    async def disconnect_from_jockey(self, thread_id: str):
        """Clean up Jockey queue"""
        if thread_id in self._jockey_queues:
            del self._jockey_queues[thread_id]
            logger.debug(f"Cleaned up Jockey queue for thread {thread_id}")
