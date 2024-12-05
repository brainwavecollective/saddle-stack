# app/schemas/jockey.py

from pydantic import BaseModel, Field, HttpUrl
from typing import Dict, Any, Optional, List, Union, Literal
from enum import Enum
from datetime import datetime

class StreamMode(str, Enum):
    """Available streaming modes"""
    MESSAGES = "messages"
    EVENTS = "events"
    ALL = "all"

class RunStatus(str, Enum):
    """Status states for a run"""
    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class JockeyRequest(BaseModel):
    text: str = Field(..., description="The text to be processed")
    thread_id: Optional[str] = Field(None, pattern="^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")
    assistant_id: Optional[str] = Field(None, pattern="^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")
    context: Optional[Dict[str, Any]] = Field(default_factory=dict)
    stream_mode: StreamMode = Field(default=StreamMode.MESSAGES)
    index_id: str = Field(..., description="Index ID for video search") 

class JockeyResponse(BaseModel):
    """Response model for Jockey processing results"""
    type: str = Field(..., description="Type of response (message, error, etc.)")
    content: Optional[str] = Field(None, description="Content of the response")
    status: str = Field(..., description="Status of the response (streaming, complete, error)")
    operation_id: str = Field(..., description="Unique identifier for the operation")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata")
    thread_id: Optional[str] = Field(None, description="Associated thread ID")
    assistant_id: Optional[str] = Field(None, description="ID of the assistant providing the response")
    
class AssistantInfo(BaseModel):
    """Information about an available assistant"""
    assistant_id: str = Field(..., description="Unique identifier for the assistant")
    name: str = Field(..., description="Display name of the assistant")
    description: str = Field(..., description="Description of the assistant's capabilities")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional assistant metadata")
    capabilities: List[str] = Field(default_factory=list, description="List of assistant capabilities")
    created_at: datetime = Field(..., description="Timestamp when the assistant was created")

class ThreadCreate(BaseModel):
    """Request model for creating a new thread"""
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Optional thread metadata")

class Thread(BaseModel):
    """Thread model containing conversation information"""
    thread_id: str = Field(..., description="Unique identifier for the thread")
    created_at: datetime = Field(..., description="Timestamp when the thread was created")
    updated_at: datetime = Field(..., description="Timestamp of last thread update")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Thread metadata")
    status: str = Field(default="active", description="Current thread status")

class RunCreate(BaseModel):
    """Request model for creating a new run"""
    thread_id: str = Field(..., description="Thread ID to create the run in")
    assistant_id: str = Field(..., description="Assistant ID to use for the run")
    input: str = Field(..., description="Input text for the run")
    stream_mode: StreamMode = Field(default=StreamMode.MESSAGES, description="Streaming mode for the run")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Optional run metadata")

class Run(BaseModel):
    """Model representing a run within a thread"""
    run_id: str = Field(..., description="Unique identifier for the run")
    thread_id: str = Field(..., description="Thread ID this run belongs to")
    assistant_id: str = Field(..., description="Assistant ID used for this run")
    status: RunStatus = Field(..., description="Current status of the run")
    created_at: datetime = Field(..., description="Timestamp when the run was created")
    started_at: Optional[datetime] = Field(None, description="Timestamp when the run started")
    completed_at: Optional[datetime] = Field(None, description="Timestamp when the run completed")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Run metadata")
    error: Optional[Dict[str, Any]] = Field(None, description="Error information if run failed")

class StreamEvent(BaseModel):
    """Model for streaming events"""
    event_type: str = Field(..., description="Type of streaming event")
    data: Dict[str, Any] = Field(..., description="Event data")
    timestamp: datetime = Field(..., description="Event timestamp")
    run_id: str = Field(..., description="Associated run ID")
    thread_id: str = Field(..., description="Associated thread ID")
    sequence_number: int = Field(..., description="Event sequence number")

class JockeyStreamState(BaseModel):
    """State management for streaming operations"""
    thread_id: str
    operation_id: str
    run_id: Optional[str] = Field(None, description="ID of the current run")
    status: str = Field(default="active")
    stream_mode: StreamMode = Field(default=StreamMode.MESSAGES)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    last_event_sequence: Optional[int] = Field(None, description="Sequence number of last processed event")

    class Config:
        json_schema_extra = {
            "example": {
                "thread_id": "123e4567-e89b-12d3-a456-426614174000",
                "operation_id": "987fcdeb-51a2-43f7-938c-927184d23000",
                "run_id": "456e6789-e89b-12d3-a456-426614174000",
                "status": "active",
                "stream_mode": "messages",
                "metadata": {},
                "last_event_sequence": 42
            }
        }