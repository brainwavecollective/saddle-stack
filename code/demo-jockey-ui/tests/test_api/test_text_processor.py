import pytest
from fastapi.testclient import TestClient
from app.main import app

@pytest.fixture
def client(app_with_mocked_services):
    return TestClient(app)

def test_process_text_success(client):
    """Test successful text processing"""
    response = client.post(
        "/api/process",
        json={"text": "Test input text"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "operation_id" in data
    assert "audio_urls" in data
    assert "main" in data["audio_urls"]
    assert "secondary" in data["audio_urls"]
    
def test_process_text_empty(client):
    """Test with empty text"""
    response = client.post(
        "/api/process",
        json={"text": ""}
    )
    assert response.status_code == 422

def test_process_text_missing_text(client):
    """Test with missing text field"""
    response = client.post(
        "/api/process",
        json={}
    )
    assert response.status_code == 422

@pytest.mark.asyncio
async def test_websocket_connection(client):
    """Test WebSocket connection"""
    with client.websocket_connect("/ws") as websocket:
        data = {"type": "test"}
        websocket.send_json(data)
        response = websocket.receive_json()
        assert response["type"] == "acknowledgment"
        assert "timestamp" in response

@pytest.mark.asyncio
async def test_process_text_broadcasts(client, monkeypatch):
    """Test that processing broadcasts updates via WebSocket"""
    connected_websockets = []
    
    async def mock_broadcast(message):
        for ws in connected_websockets:
            await ws.send_json(message)
    
    from app.api.endpoints.websocket import connection_manager
    monkeypatch.setattr(connection_manager, "broadcast", mock_broadcast)
    
    with client.websocket_connect("/ws") as websocket:
        connected_websockets.append(websocket)
        
        # Send processing request
        client.post(
            "/api/process",
            json={"text": "Test input text"}
        )
        
        # Check for broadcast message
        response = websocket.receive_json()
        assert response["type"] == "processing_update"
        assert response["status"] == "audio_generated"
        
        connected_websockets.remove(websocket)