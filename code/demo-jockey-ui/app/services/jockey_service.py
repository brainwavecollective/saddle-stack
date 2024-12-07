"""
Brain Wave Collective
https://brainwavecollective.ai
  Revolutionizing Video Creation with TwelveLabs Jockey and NVIDIA AI Workbench. 
  Saddle Stack (AKA Jockbench) is our submission to the Dell x NVIDIA HackAI Challenge
File: jockey_service.py
Created: 2024
Authors: Thienthanh Trinh & Daniel Ritchie
Copyright (c) 2024 Brain Wave Collective
"""

# app/services/jockey_service.py

from typing import AsyncGenerator, Dict, Any, Optional, List
import uuid
from loguru import logger
import time
import aiohttp
from aiohttp import TCPConnector
import backoff
from app.core.config import get_settings
from app.schemas.jockey import JockeyResponse
import json

class JockeyService:
    def __init__(self):
        self.settings = get_settings()
        if not self.settings.jockey_api_url:
            raise ValueError("JOCKEY_API_URL not configured")
        self.timeout = aiohttp.ClientTimeout(total=360, connect=10)
        self.session = None
        self.default_assistant_id = None  # Will store default assistant ID
        logger.info(f"JockeyService initialized with URL: {self.settings.jockey_api_url}")

    @staticmethod
    def extract_display_content(data):
        """Extract only the content that should be displayed to the user."""
        if isinstance(data, dict):
            # If we have chat history, only extract the content from messages
            if 'chat_history' in data:
                messages = []
                for msg in data['chat_history']:
                    # Skip system messages and only take the most recent message
                    if msg.get('type') not in ['system'] and 'content' in msg:
                        messages.append({
                            'content': msg['content'],
                            'type': msg.get('type', 'unknown'),
                            'name': msg.get('name')
                        })
                if messages:
                    # Only return the most recent message
                    return messages[-1]
            
            # If it's a tool call that produced output, format it nicely
            if 'tool_calls' in data:
                tool_outputs = []
                for tool in data['tool_calls']:
                    if tool.get('output'):
                        tool_outputs.append({
                            'content': f"Completed {tool.get('name', 'operation')}",
                            'type': 'tool_output'
                        })
                if tool_outputs:
                    return tool_outputs[-1]

        return None


    async def initialize(self):
        """Initialize the service and set up default assistant"""
        assistants = await self.search_assistants()
        if not assistants:
            raise ValueError("No assistants available")
        # Look for assistant_id instead of id in the response
        self.default_assistant_id = assistants[0].get('assistant_id')
        if not self.default_assistant_id:
            raise ValueError("Invalid assistant data - missing assistant_id")
        logger.info(f"Initialized with default assistant ID: {self.default_assistant_id}")

    async def _ensure_connection(self) -> None:
        """Ensure we have a valid session"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                timeout=self.timeout,
                headers={"Content-Type": "application/json"}
            )
            logger.info("Created new aiohttp session")

    @backoff.on_exception(
        backoff.expo,
        (aiohttp.ClientError, aiohttp.ServerTimeoutError),
        max_tries=3
    )
    async def search_assistants(self) -> List[Dict[str, Any]]:
        """Get list of available assistants"""
        await self._ensure_connection()
        try:
            # Add logging to see exact URL being called
            url = f"{self.settings.jockey_api_url}/assistants/search"
            logger.debug(f"Fetching assistants from: {url}")
            
            async with self.session.post(  # Changed from GET to POST
                url,
                json={}  # Empty payload but using POST
            ) as response:
                if response.status != 200:
                    error = await response.text()
                    logger.error(f"Failed to fetch assistants: {error}")
                    raise ValueError(f"Server error: {error}")
                
                data = await response.json()
                logger.debug(f"Received assistants data: {data}")
                return data
                
        except Exception as e:
            logger.error(f"Error fetching assistants: {str(e)}")
            raise

    async def create_thread(self) -> Dict[str, Any]:
        """Create a new conversation thread"""
        await self._ensure_connection()
        try:
            async with self.session.post(
                f"{self.settings.jockey_api_url}/threads/create"
            ) as response:
                if response.status != 200:
                    error = await response.text()
                    logger.error(f"Failed to create thread: {error}")
                    raise ValueError(f"Server error: {error}")
                return await response.json()
        except Exception as e:
            logger.error(f"Error creating thread: {str(e)}")
            raise

    async def list_runs(self, thread_id: str) -> List[Dict[str, Any]]:
        """List all runs for a specific thread"""
        await self._ensure_connection()
        try:
            async with self.session.get(
                f"{self.settings.jockey_api_url}/runs/list",
                params={"thread_id": thread_id}
            ) as response:
                if response.status != 200:
                    error = await response.text()
                    logger.error(f"Failed to list runs: {error}")
                    raise ValueError(f"Server error: {error}")
                return await response.json()
        except Exception as e:
            logger.error(f"Error listing runs: {str(e)}")
            raise


    def ensure_valid_state(self, state_update: dict) -> dict:
        """Ensure state updates maintain required structure"""
        # Start with current values from state_update
        base_state = {
            'chat_history': state_update.get('chat_history', []),
            'next_worker': state_update.get('next_worker', 'planner'),  # Default to planner
            'made_plan': state_update.get('made_plan', False),
            'active_plan': state_update.get('active_plan', None)
        }

        # Ensure chat_history is always a list
        if not isinstance(base_state['chat_history'], list):
            base_state['chat_history'] = [base_state['chat_history']] if base_state['chat_history'] else []

        # Ensure next_worker is never an empty string
        if base_state['next_worker'] == "":
            base_state['next_worker'] = 'planner'

        # Ensure active_plan is never an empty string
        if base_state['active_plan'] == "":
            base_state['active_plan'] = None

        # Ensure at least one field is set
        if not any(base_state.values()):
            base_state['made_plan'] = False
            base_state['next_worker'] = 'planner'

        return base_state
        
    async def stream_processing(
            self,
            text: str,
            index_id: Optional[str] = None,
            assistant_id: Optional[str] = None,
            thread_id: Optional[str] = None,
            stream_mode: str = "messages"
        ) -> AsyncGenerator[JockeyResponse, None]:

            operation_id = str(uuid.uuid4())
            logger.debug(f"Starting stream_processing operation {operation_id}")
            
            if not index_id:
                index_id = self.settings.twelve_labs_index_id
                logger.debug(f"Using default index_id: {index_id}")
            
            if not index_id:
                error_msg = "Index ID must be provided for video processing."
                logger.error(f"[{operation_id}] {error_msg}")
                yield JockeyResponse(
                    type="error",
                    content=error_msg,
                    status="error",
                    operation_id=operation_id
                )
                return
            
            if assistant_id is None:
                if self.default_assistant_id is None:
                    await self.initialize()
                assistant_id = self.default_assistant_id
                logger.debug(f"Using assistant_id: {assistant_id}")

            await self._ensure_connection()
            try:
                # Initialize state
                current_state = {
                    "chat_history": [
                        {
                            "type": "user",
                            "content": f"{index_id} {text}",
                            "additional_kwargs": {},
                            "response_metadata": {},
                            "id": str(uuid.uuid4()),
                            "example": False,
                            "name": ""
                        }
                    ],
                    "next_worker": "planner",
                    "made_plan": False,
                    "active_plan": ""
                }

                # Track seen messages and states
                seen_messages = set()
                last_chat_length = 0
                seen_content_hashes = set()

                formatted_input = {
                    "assistant_id": assistant_id,
                    "index_id": index_id,
                    "thread_id": thread_id,
                    "input": current_state
                }

                params = {
                    "streamMode": stream_mode,
                    "thread_id": thread_id,
                    "index_id": index_id 
                }

                yield JockeyResponse(
                    type="message",
                    content="Connecting to Jockey server...",
                    status="connecting",
                    operation_id=operation_id
                )
                
                
                
                async with self.session.post(
                    f"{self.settings.jockey_api_url}/runs/stream",
                    params=params,
                    json=formatted_input
                ) as response:
                    logger.debug(f"[{operation_id}] Server response status: {response.status}")
                    # Add this detailed logging
                    logger.debug(f"[{operation_id}] Request details:")
                    logger.debug(f"[{operation_id}] - URL: {self.settings.jockey_api_url}/runs/stream")
                    logger.debug(f"[{operation_id}] - Params: {params}")
                    logger.debug(f"[{operation_id}] - Input payload: {formatted_input}")
                    logger.debug(f"[{operation_id}] - Full request params: {json.dumps(params, indent=2)}")
                    logger.debug(f"[{operation_id}] - Full request payload: {json.dumps(formatted_input, indent=2)}")                   
                    
                    if response.status != 200:
                        error = await response.text()
                        logger.error(f"[{operation_id}] Server returned {response.status}: {error}")
                        yield JockeyResponse(
                            type="error",
                            content=f"Server error: {error}",
                            status="error",
                            operation_id=operation_id
                        )
                        return

                    logger.debug(f"[{operation_id}] Starting to read response stream")
                    async for line in response.content:
                        if line:
                            try:
                                content = line.decode().strip()
                                
                                if content and content != ": heartbeat":
                                    # Always process error messages
                                    if ": error" in content.lower():
                                        logger.error(f"[{operation_id}] Server error details:")
                                        logger.error(f"[{operation_id}] - Raw error content: {content}")
                                        logger.error(f"[{operation_id}] - Current state: {json.dumps(current_state, indent=2)}")
                                        logger.error(f"[{operation_id}] - Last successful response: {last_chat_length}")
                                        logger.error(f"[{operation_id}] - Response status: {response.status}")
                                        logger.error(f"[{operation_id}] - Response headers: {dict(response.headers)}")
                                        try:
                                            error_body = await response.text()
                                            logger.error(f"[{operation_id}] - Full error response body: {error_body}")
                                        except Exception as e:
                                            logger.error(f"[{operation_id}] - Could not read error body: {str(e)}")
                                        yield JockeyResponse(
                                            type="error",
                                            content=content,
                                            status="error",
                                            operation_id=operation_id
                                        )
                                        continue

                                    # Handle events
                                    if content.startswith("event: "):
                                        event_type = content.split("event: ")[1].strip()
                                        # Only yield new event types
                                        if event_type not in seen_messages:
                                            seen_messages.add(event_type)
                                            yield JockeyResponse(
                                                type="event",
                                                content=event_type,
                                                status="streaming",
                                                operation_id=operation_id
                                            )
                                    
                                    # Handle data
                                    elif content.startswith("data: "):
                                        data = content.split("data: ")[1].strip()
                                        try:
                                            data_json = json.loads(data)
                                            if isinstance(data_json, dict):
                                                # Ensure valid state
                                                validated_state = self.ensure_valid_state(data_json)
                                                logger.debug(f"[{operation_id}] Validated state: {validated_state}")
                                                
                                                # Update current state safely
                                                current_state.update(validated_state)
                                                
                                                # Check for new chat messages using validated state
                                                chat_history = validated_state.get('chat_history', [])
                                                if len(chat_history) > last_chat_length:
                                                    # Process only new messages
                                                    new_messages = chat_history[last_chat_length:]
                                                    new_content = False
                                                    
                                                    for msg in new_messages:
                                                        content = msg.get('content', '')
                                                        content_hash = hash(content)
                                                        if content_hash not in seen_content_hashes:
                                                            seen_content_hashes.add(content_hash)
                                                            new_content = True
                                                    
                                                    if new_content:
                                                        last_chat_length = len(chat_history)
                                                        # Replace this yield with our new display content extraction
                                                        display_content = self.extract_display_content(validated_state)
                                                        if display_content:
                                                            yield JockeyResponse(
                                                                type="data",
                                                                content=json.dumps(display_content),  # Only send extracted content
                                                                status="streaming",
                                                                operation_id=operation_id
                                                            )
                                                
                                                # Handle state updates
                                                if data_json.get("run_id"):
                                                    validated_state = self.ensure_valid_state(data_json)
                                                    
                                                    # Only include keys with non-empty values but ensure at least one field
                                                    filtered_values = {
                                                        key: value for key, value in validated_state.items()
                                                        if value is not None and (not isinstance(value, list) or value)
                                                    }

                                                    # Always ensure at least one field is present
                                                    if not filtered_values:
                                                        filtered_values["chat_history"] = validated_state.get("chat_history", [])
                                                        # If still empty, add default values
                                                        if not filtered_values["chat_history"]:
                                                            filtered_values["made_plan"] = False
                                                            filtered_values["next_worker"] = "planner"

                                                    update_payload = {
                                                        "values": filtered_values
                                                    }

                                                    logger.debug(f"[{operation_id}] Sending state update: {json.dumps(update_payload, indent=2)}")

                                                    if not update_payload["values"]:  # Final safety check
                                                        logger.warning(f"[{operation_id}] Skipping state update: No valid data to send")
                                                    else:
                                                        await self.session.post(
                                                            f"{self.settings.jockey_api_url}/runs",
                                                            params={"run_id": data_json["run_id"]},
                                                            json=update_payload
                                                        )
                                        except json.JSONDecodeError:
                                            logger.warning(f"[{operation_id}] Failed to parse JSON data: {data}")
                                        except Exception as e:
                                            logger.error(f"[{operation_id}] Error processing data update: {str(e)}")

                                    
                                    # Handle other messages
                                    else:
                                        msg_hash = hash(content)
                                        if msg_hash not in seen_messages:
                                            seen_messages.add(msg_hash)
                                            yield JockeyResponse(
                                                type="message",
                                                content=content,
                                                status="streaming",
                                                operation_id=operation_id
                                            )
                                            
                            except Exception as e:
                                logger.error(f"[{operation_id}] Error processing line: {str(e)}")
                                continue
                                
            except aiohttp.ClientError as e:
                logger.error(f"[{operation_id}] Connection error: {str(e)}")
                yield JockeyResponse(
                    type="error",
                    content=f"Connection error: {str(e)}",
                    status="error",
                    operation_id=operation_id
                )
            except Exception as e:
                error_details = {
                    'type': type(e).__name__,
                    'message': str(e),
                    'repr': repr(e),
                }
                logger.error(f"[{operation_id}] Exception details: {error_details}")
                logger.error(f"[{operation_id}] Full traceback: {traceback.format_exc()}")
                yield JockeyResponse(
                    type="error",
                    content=f"Unexpected error: {str(e)}",
                    status="error",
                    operation_id=operation_id
                )
            finally:
                logger.info(f"[{operation_id}] Completed processing")