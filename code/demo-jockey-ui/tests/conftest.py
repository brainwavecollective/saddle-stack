# conftest.py
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.config import get_settings
import asyncio

@pytest.fixture
def settings():
    """Provide test settings"""
    return get_settings()

@pytest.fixture
def event_loop():
    """Create an instance of the default event loop for each test case."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def test_client(app_with_mocked_services):
    """Create test client with mocked services"""
    with TestClient(app_with_mocked_services) as client:
        yield client

# test_text_processor.py
import pytest
from fastapi.testclient import TestClient
import json

def test_process_text_success(test_client):
    """Test successful text processing"""
    response = test_client.post(
        "/api/process",
        json={"text": "Test input text"}
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # Verify response structure
    assert "operation_id" in data
    assert "audio_urls" in data
    assert "main" in data["audio_urls"]
    assert "secondary" in data["audio_urls"]
    assert "response" in data
    assert "timeline" in data

def test_process_text_empty(test_client):
    """Test with empty text"""
    response = test_client.post(
        "/api/process",
        json={"text": ""}
    )
    assert response.status_code == 422

def test_process_text_missing_text(test_client):
    """Test with missing text field"""
    response = test_client.post(
        "/api/process",
        json={}
    )
    assert response.status_code == 422

@pytest.mark.asyncio
async def test_websocket_connection():
    """Test WebSocket connection"""
    async with TestClient(app) as client:
        with client.websocket_connect("/ws") as websocket:
            data = {"type": "test"}
            websocket.send_json(data)
            response = websocket.receive_json()
            assert response["type"] == "acknowledgment"
            assert "timestamp" in response

@pytest.mark.asyncio
async def test_process_text_broadcasts():
    """Test that processing broadcasts updates via WebSocket"""
    async with TestClient(app) as client:
        with client.websocket_connect("/ws") as websocket:
            response = client.post(
                "/api/process",
                json={"text": "Test input text"}
            )
            assert response.status_code == 200
            
            # Check for broadcast message
            broadcast = websocket.receive_json()
            assert broadcast["type"] == "processing_update"
            assert broadcast["status"] == "audio_generated"

