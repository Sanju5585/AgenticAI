"""
A2UI Protocol Server - Application-to-UI Communication Protocol
This server manages real-time UI state updates and bidirectional communication
between the backend application and frontend UI.
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, Literal
import asyncio
import json
import uuid
import logging
from datetime import datetime
from collections import defaultdict
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="A2UI Protocol Server", version="1.0.0")

# Enable CORS for frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# DATA MODELS
# ============================================================================

class UIStateUpdate(BaseModel):
    """Model for UI state updates sent from backend to frontend"""
    update_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    module: str = Field(..., description="Module name (e.g., 'product_search', 'cart', 'checkout')")
    action: str = Field(..., description="Action type (e.g., 'update', 'replace', 'append', 'remove')")
    component: str = Field(..., description="UI component to update (e.g., 'product_list', 'loading_state')")
    data: Dict[str, Any] = Field(..., description="Data payload for the update")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional metadata")

class UICommand(BaseModel):
    """Model for UI commands sent from backend to frontend"""
    command_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    module: str
    command: Literal["navigate", "show_modal", "show_toast", "update_state", "refresh", "scroll_to"]
    params: Dict[str, Any]

class ClientMessage(BaseModel):
    """Model for messages sent from frontend to backend"""
    message_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    module: str
    event: str = Field(..., description="Event type (e.g., 'search', 'click', 'submit')")
    data: Dict[str, Any]

class SubscriptionRequest(BaseModel):
    """Model for module subscription requests"""
    session_id: str
    modules: List[str] = Field(..., description="List of modules to subscribe to")

# ============================================================================
# CONNECTION MANAGER
# ============================================================================

class ConnectionManager:
    """Manages WebSocket connections and message routing"""
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.module_subscriptions: Dict[str, set] = defaultdict(set)  # session_id -> {modules}
        self.session_metadata: Dict[str, Dict[str, Any]] = {}
        
    async def connect(self, websocket: WebSocket, session_id: str):
        """Accept and register a new WebSocket connection"""
        await websocket.accept()
        self.active_connections[session_id] = websocket
        self.session_metadata[session_id] = {
            "connected_at": datetime.utcnow().isoformat(),
            "last_activity": datetime.utcnow().isoformat()
        }
        logger.info(f"✅ Client connected: {session_id}")
        
    def disconnect(self, session_id: str):
        """Remove a WebSocket connection"""
        if session_id in self.active_connections:
            del self.active_connections[session_id]
        if session_id in self.module_subscriptions:
            del self.module_subscriptions[session_id]
        if session_id in self.session_metadata:
            del self.session_metadata[session_id]
        logger.info(f"❌ Client disconnected: {session_id}")
        
    async def send_to_session(self, session_id: str, message: dict):
        """Send message to a specific session"""
        if session_id in self.active_connections:
            try:
                logger.info(f"📤 Sending to session {session_id}: {message.get('type')} - {message.get('component')}")
                await self.active_connections[session_id].send_json(message)
                self.session_metadata[session_id]["last_activity"] = datetime.utcnow().isoformat()
                logger.info(f"✅ Message sent successfully to {session_id}")
            except Exception as e:
                logger.error(f"Error sending to {session_id}: {e}")
                self.disconnect(session_id)
        else:
            logger.warning(f"⚠️ Session {session_id} not found in active connections")
            logger.info(f"   Active sessions: {list(self.active_connections.keys())}")
                
    async def broadcast_to_module(self, module: str, message: dict):
        """Broadcast message to all sessions subscribed to a module"""
        disconnected_sessions = []
        for session_id, subscribed_modules in self.module_subscriptions.items():
            if module in subscribed_modules:
                try:
                    await self.send_to_session(session_id, message)
                except Exception as e:
                    logger.error(f"Error broadcasting to {session_id}: {e}")
                    disconnected_sessions.append(session_id)
        
        # Clean up disconnected sessions
        for session_id in disconnected_sessions:
            self.disconnect(session_id)
            
    def subscribe_to_modules(self, session_id: str, modules: List[str]):
        """Subscribe a session to specific modules"""
        self.module_subscriptions[session_id].update(modules)
        logger.info(f"📡 Session {session_id} subscribed to: {modules}")
        
    def get_connection_stats(self) -> dict:
        """Get statistics about active connections"""
        return {
            "total_connections": len(self.active_connections),
            "sessions": list(self.active_connections.keys()),
            "module_subscriptions": {
                session_id: list(modules) 
                for session_id, modules in self.module_subscriptions.items()
            }
        }

manager = ConnectionManager()

# ============================================================================
# WEBSOCKET ENDPOINTS
# ============================================================================

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """
    Main WebSocket endpoint for A2UI protocol communication
    """
    await manager.connect(websocket, session_id)
    
    try:
        # Send connection confirmation
        await websocket.send_json({
            "type": "connection_established",
            "session_id": session_id,
            "timestamp": datetime.utcnow().isoformat(),
            "message": "Connected to A2UI Protocol Server"
        })
        
        # Listen for incoming messages
        while True:
            data = await websocket.receive_json()
            
            # Handle subscription requests
            if data.get("type") == "subscribe":
                modules = data.get("modules", [])
                manager.subscribe_to_modules(session_id, modules)
                await websocket.send_json({
                    "type": "subscription_confirmed",
                    "modules": modules,
                    "session_id": session_id
                })
                
            # Handle client events
            elif data.get("type") == "event":
                logger.info(f"📨 Event from {session_id}: {data.get('event')}")
                # You can add custom event handlers here
                
            # Handle heartbeat/ping
            elif data.get("type") == "ping":
                await websocket.send_json({
                    "type": "pong",
                    "timestamp": datetime.utcnow().isoformat()
                })
                
    except WebSocketDisconnect:
        manager.disconnect(session_id)
    except Exception as e:
        logger.error(f"WebSocket error for {session_id}: {e}")
        manager.disconnect(session_id)

# ============================================================================
# HTTP API ENDPOINTS
# ============================================================================

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "A2UI Protocol Server",
        "version": "1.0.0",
        "active_connections": len(manager.active_connections)
    }

@app.get("/stats")
async def get_stats():
    """Get server statistics"""
    return manager.get_connection_stats()

@app.post("/api/ui/update")
async def send_ui_update(update: UIStateUpdate):
    """
    Send a UI state update to all clients subscribed to the module
    
    Example:
    {
        "module": "product_search",
        "action": "update",
        "component": "product_list",
        "data": {
            "products": [...]
        }
    }
    """
    message = {
        "type": "ui_update",
        **update.model_dump()
    }
    
    await manager.broadcast_to_module(update.module, message)
    
    return {
        "status": "sent",
        "update_id": update.update_id,
        "module": update.module
    }

@app.post("/api/ui/command")
async def send_ui_command(command: UICommand):
    """
    Send a UI command to clients
    
    Example:
    {
        "module": "product_search",
        "command": "show_toast",
        "params": {
            "message": "Products loaded successfully",
            "type": "success"
        }
    }
    """
    message = {
        "type": "ui_command",
        **command.model_dump()
    }
    
    await manager.broadcast_to_module(command.module, message)
    
    return {
        "status": "sent",
        "command_id": command.command_id,
        "module": command.module
    }

@app.post("/api/ui/update/{session_id}")
async def send_ui_update_to_session(session_id: str, update: UIStateUpdate):
    """Send a UI update to a specific session"""
    logger.info(f"📥 Received UI update for session: {session_id}")
    logger.info(f"   Module: {update.module}")
    logger.info(f"   Component: {update.component}")
    logger.info(f"   Action: {update.action}")
    logger.info(f"   Data keys: {list(update.data.keys())}")
    
    message = {
        "type": "ui_update",
        **update.model_dump()
    }
    
    logger.info(f"📤 Sending message to session {session_id}")
    await manager.send_to_session(session_id, message)
    logger.info(f"✅ Message sent successfully")
    
    return {
        "status": "sent",
        "update_id": update.update_id,
        "session_id": session_id
    }

# ============================================================================
# STARTUP & SHUTDOWN EVENTS
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Handle startup events"""
    logger.info("=" * 60)
    logger.info("A2UI Protocol Server Starting...")
    logger.info("WebSocket endpoint: /ws/{session_id}")
    logger.info("HTTP API: /api/ui/update, /api/ui/command")
    await asyncio.sleep(0.5)
    logger.info("✅ A2UI Protocol Server Ready!")
    logger.info("=" * 60)

@app.on_event("shutdown")
async def shutdown_event():
    """Handle shutdown events"""
    logger.info("A2UI Protocol Server Shutting Down...")
    # Disconnect all active connections
    for session_id in list(manager.active_connections.keys()):
        manager.disconnect(session_id)
    logger.info("Cleanup completed")

# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("A2UI_PORT", "8020"))
    uvicorn.run(app, host="0.0.0.0", port=port)
