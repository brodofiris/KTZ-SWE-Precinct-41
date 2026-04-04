import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from typing import List
from contextlib import asynccontextmanager

# Import your existing logic
from database import init_db
from ingester import TelemetryIngester
from schemas import TelemetryEntry
from database import get_historical_telemetry

from datetime import datetime
from typing import Optional


# --- Lifespan Manager ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # [STARTUP] Logic goes here
    print("Starting up: Initializing database and ingester...")
    await init_db()
    
    # Initialize ingester
    ingester = TelemetryIngester("train_telemetry.json")
    
    # Create the background task
    # We store it in a variable so we can potentially cancel it on shutdown
    task = asyncio.create_task(ingester.start_watching(websocket_callback))
    
    yield  # The server runs while this yield is "active"
    
    # [SHUTDOWN] Logic goes here
    print("Shutting down: Cancelling background tasks...")
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        print("Ingester task stopped successfully.")

# Pass the lifespan to the FastAPI constructor
app = FastAPI(title="Train Telemetry API", lifespan=lifespan)

# --- WebSocket Manager ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                # Handle stale connections
                continue

manager = ConnectionManager()

# --- The Bridge Callback ---
async def websocket_callback(data: TelemetryEntry, error_msg: str):
    """
    This replaces your CLI-only callback. 
    It sends data to the DB and broadcasts to WebSockets.
    """
    if data:
        # 1. (Optional) Insert to DB - reuse your existing logic
        # from database import insert_telemetry
        # await insert_telemetry(data)
        
        # 2. Broadcast to all web clients
        # .model_dump_json() handles the datetime serialization automatically
        await manager.broadcast(data.model_dump(mode='json'))
    
    if error_msg != "None":
        await manager.broadcast({"error": error_msg})


# --- Endpoints ---
@app.get("/")
async def root():
    return {"status": "Train Telemetry Server Online", "version": "1.0.0"}

@app.get("/history")
async def get_history(
    limit: int = 100, 
    start_date: Optional[datetime] = None, 
    end_date: Optional[datetime] = None
):
    """
    Returns historical telemetry records.
    Optionally filter by start_date and end_date (ISO 8601 format).
    """
    data = await get_historical_telemetry(limit, start_date, end_date)
    return data

@app.websocket("/ws/telemetry")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Keep the connection open and wait for messages from client if needed
            await websocket.receive_text() 
    except WebSocketDisconnect:
        manager.disconnect(websocket)