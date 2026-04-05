
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from typing import List
from contextlib import asynccontextmanager
from fastapi.responses import FileResponse
from datetime import datetime
from typing import Optional
from sqlalchemy import select
from fastapi.staticfiles import StaticFiles


# main logic
from src.database import init_db, get_historical_telemetry, User, AsyncSessionLocal
from src.ingester import TelemetryIngester
from src.schemas import TelemetryEntry, UserCreate
from src.auth import create_token, verify_token, get_password_hash, verify_password

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")


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
# mount the static lib
app.mount("/static", StaticFiles(directory="static"), name="static")

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
    """Serves the main frontend dashboard."""
    return FileResponse("index.html")

# --- Security Dependency ---
async def get_current_user(token: str = Depends(oauth2_scheme)):
    """Validates the token and returns the user payload."""
    payload = verify_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload

@app.get("/history")
async def get_history(
    limit: int = 100, 
    start_date: Optional[datetime] = None, 
    end_date: Optional[datetime] = None,
    current_user: dict = Depends(get_current_user) # NEW: This protects the route
):
    """
    Returns historical telemetry records.
    Requires a valid JWT token.
    """
    # You can even check roles here, e.g., if current_user['role'] == 'admin'
    data = await get_historical_telemetry(limit, start_date, end_date)
    return data

@app.websocket("/ws/telemetry")
async def websocket_endpoint(websocket: WebSocket, token: str): # NEW: Require token in URL
    # Validate the token before accepting the connection
    user_payload = verify_token(token)
    
    if user_payload is None:
        # Close connection if unauthorized
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text() 
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# --- Authentication Endpoints ---
@app.post("/signup")
async def signup(user_data: UserCreate):
    async with AsyncSessionLocal() as session:
        # 1. Check if operator ID is already taken
        query = select(User).where(User.operator_id == user_data.operator_id)
        result = await session.execute(query)
        if result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Operator ID already registered")
        
        # 2. Create new user with hashed password
        new_user = User(
            first_name=user_data.first_name,
            last_name=user_data.last_name,
            operator_id=user_data.operator_id,
            hashed_password=get_password_hash(user_data.password)
        )
        session.add(new_user)
        await session.commit()
        return {"message": "Operator registered successfully"}

@app.post("/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    async with AsyncSessionLocal() as session:
        # 1. Find the user by operator_id (which acts as the username)
        query = select(User).where(User.operator_id == form_data.username)
        result = await session.execute(query)
        user = result.scalar_one_or_none()
        
        # 2. Verify user exists AND password is correct
        if not user or not verify_password(form_data.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect Operator ID or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
            
        # 3. Issue the token
        token = create_token(user_id=user.id, role=user.role)
        return {
            "access_token": token,
            "token_type": "bearer",
            "first_name": user.first_name,
            "last_name": user.last_name,
            "role": user.role
        }