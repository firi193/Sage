"""
Sage API Key Manager - FastAPI Backend
Serves both API endpoints and static frontend files
"""

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional
import os
import uvicorn
from datetime import datetime, timedelta
import json

# Initialize FastAPI app
app = FastAPI(
    title="Sage API Key Manager",
    description="API Key Management System with Usage Tracking",
    version="1.0.0"
)

# CORS middleware for cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure properly for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models for request/response
class KeyCreate(BaseModel):
    key_name: str
    environment: str
    api_key: str

class GrantCreate(BaseModel):
    key_id: str
    caller_agent_id: str
    max_calls_per_day: int
    expiry_date: str

class Key(BaseModel):
    key_id: str
    key_name: str
    environment: str
    created_at: datetime
    is_active: bool = True
    grant_count: int = 0

class Grant(BaseModel):
    grant_id: str
    key_id: str
    key_name: str
    caller_id: str
    max_calls_per_day: int
    current_usage: int = 0
    expires_at: datetime
    created_at: datetime
    is_active: bool = True

class LogEntry(BaseModel):
    id: str
    timestamp: datetime
    caller_id: str
    key_id: str
    key_name: str
    endpoint: str
    response_code: int
    response_time: int
    method: str = "POST"

# In-memory storage (replace with database in production)
keys_db = []
grants_db = []
logs_db = []

# API Routes
@app.get("/api/v1/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "sage-api",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/v1/keys", response_model=List[Key])
async def list_keys():
    """List all API keys"""
    return keys_db

@app.post("/api/v1/keys")
async def add_key(key_data: KeyCreate):
    """Add a new API key"""
    key_id = f"key-{len(keys_db) + 1}-{int(datetime.now().timestamp())}"
    
    new_key = Key(
        key_id=key_id,
        key_name=key_data.key_name,
        environment=key_data.environment,
        created_at=datetime.now(),
        is_active=True,
        grant_count=0
    )
    
    keys_db.append(new_key)
    return {"message": "Key added successfully", "key_id": key_id}

@app.delete("/api/v1/keys/{key_id}")
async def delete_key(key_id: str):
    """Delete an API key"""
    global keys_db
    keys_db = [key for key in keys_db if key.key_id != key_id]
    return {"message": "Key deleted successfully"}

@app.get("/api/v1/grants", response_model=List[Grant])
async def list_grants(key_id: Optional[str] = None):
    """List access grants, optionally filtered by key"""
    if key_id:
        return [grant for grant in grants_db if grant.key_id == key_id]
    return grants_db

@app.post("/api/v1/grants")
async def create_grant(grant_data: GrantCreate):
    """Create a new access grant"""
    grant_id = f"grant-{len(grants_db) + 1}-{int(datetime.now().timestamp())}"
    
    # Find the key to get its name
    key = next((k for k in keys_db if k.key_id == grant_data.key_id), None)
    if not key:
        raise HTTPException(status_code=404, detail="Key not found")
    
    new_grant = Grant(
        grant_id=grant_id,
        key_id=grant_data.key_id,
        key_name=key.key_name,
        caller_id=grant_data.caller_agent_id,
        max_calls_per_day=grant_data.max_calls_per_day,
        current_usage=0,
        expires_at=datetime.fromisoformat(grant_data.expiry_date),
        created_at=datetime.now(),
        is_active=True
    )
    
    grants_db.append(new_grant)
    
    # Update key grant count
    key.grant_count += 1
    
    return {"message": "Grant created successfully", "grant_id": grant_id}

@app.delete("/api/v1/grants/{grant_id}")
async def revoke_grant(grant_id: str):
    """Revoke an access grant"""
    global grants_db
    grant = next((g for g in grants_db if g.grant_id == grant_id), None)
    if grant:
        # Update key grant count
        key = next((k for k in keys_db if k.key_id == grant.key_id), None)
        if key:
            key.grant_count = max(0, key.grant_count - 1)
    
    grants_db = [grant for grant in grants_db if grant.grant_id != grant_id]
    return {"message": "Grant revoked successfully"}

@app.get("/api/v1/logs", response_model=List[LogEntry])
async def get_logs(key_id: Optional[str] = None, time_filter: str = "24h"):
    """Get usage logs with optional filtering"""
    # Generate some mock logs if none exist
    if not logs_db:
        generate_mock_logs()
    
    filtered_logs = logs_db
    
    # Filter by key if specified
    if key_id:
        filtered_logs = [log for log in filtered_logs if log.key_id == key_id]
    
    # Filter by time
    now = datetime.now()
    if time_filter == "24h":
        cutoff = now - timedelta(hours=24)
    elif time_filter == "7d":
        cutoff = now - timedelta(days=7)
    else:
        cutoff = now - timedelta(hours=24)
    
    filtered_logs = [log for log in filtered_logs if log.timestamp >= cutoff]
    
    # Sort by timestamp (newest first)
    filtered_logs.sort(key=lambda x: x.timestamp, reverse=True)
    
    return filtered_logs

def generate_mock_logs():
    """Generate mock log data for testing"""
    import random
    
    if not keys_db:
        return
    
    mock_endpoints = [
        "/api/v1/chat/completions",
        "/api/v1/embeddings", 
        "/api/v1/models",
        "/api/v1/completions",
        "/api/v1/images/generations"
    ]
    
    mock_agents = ["agent-001", "app-dashboard", "mobile-app", "web-client", "batch-processor"]
    mock_statuses = [200, 200, 200, 201, 400, 401, 429, 500]
    
    # Generate 20 mock logs
    for i in range(20):
        key = random.choice(keys_db)
        log_entry = LogEntry(
            id=f"log-{i}-{int(datetime.now().timestamp())}",
            timestamp=datetime.now() - timedelta(
                hours=random.randint(0, 168),  # Last 7 days
                minutes=random.randint(0, 59)
            ),
            caller_id=random.choice(mock_agents),
            key_id=key.key_id,
            key_name=key.key_name,
            endpoint=random.choice(mock_endpoints),
            response_code=random.choice(mock_statuses),
            response_time=random.randint(50, 2000),
            method="POST"
        )
        logs_db.append(log_entry)

# Serve static files (frontend)
app.mount("/static", StaticFiles(directory="sage_ui"), name="static")

@app.get("/")
async def serve_frontend():
    """Serve the main frontend page"""
    return FileResponse("sage_ui/index.html")

@app.get("/{path:path}")
async def serve_spa(path: str):
    """Serve SPA routes (fallback to index.html)"""
    file_path = f"sage_ui/{path}"
    if os.path.exists(file_path) and os.path.isfile(file_path):
        return FileResponse(file_path)
    return FileResponse("sage_ui/index.html")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=port,
        log_level="info"
    )