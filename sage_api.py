#!/usr/bin/env python3
"""
Sage MCP FastAPI Service

This FastAPI service exposes Sage MCP functionality as REST endpoints.
It can be used directly or wrapped as an MCP server for Coral integration.
"""

from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
import asyncio
import logging
from datetime import datetime
import os

from sage.sage_mcp import SageMCP

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Sage MCP API",
    description="Secure API Key Management and Proxying Service",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8080", "http://127.0.0.1:8080", "http://localhost:8001", "*"],  # Allow frontend origins
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Global SageMCP instance
sage_instance: Optional[SageMCP] = None


# Pydantic models for request/response validation
class AddKeyRequest(BaseModel):
    key_name: str = Field(..., description="Human-readable name for the API key")
    api_key: str = Field(..., description="The API key to store securely")
    
    class Config:
        json_schema_extra = {
            "example": {
                "key_name": "openai_production_key",
                "api_key": "sk-1234567890abcdef"
            }
        }


class AddKeyResponse(BaseModel):
    success: bool
    key_id: str = Field(..., description="Unique identifier for the stored key")
    message: str


class GrantAccessRequest(BaseModel):
    key_id: str = Field(..., description="ID of the key to grant access to")
    caller_id: str = Field(..., description="Coral session ID of the agent receiving access")
    permissions: Dict[str, Any] = Field(..., description="Permission settings")
    expiry_hours: int = Field(24, description="Grant expiry in hours")
    
    class Config:
        json_schema_extra = {
            "example": {
                "key_id": "12345678-1234-1234-1234-123456789abc",
                "caller_id": "coral_agent_bob_session_456",
                "permissions": {"max_calls_per_day": 100},
                "expiry_hours": 24
            }
        }


class GrantAccessResponse(BaseModel):
    success: bool
    message: str


class ProxyCallRequest(BaseModel):
    key_id: str = Field(..., description="ID of the key to use for the API call")
    target_url: str = Field(..., description="Target API URL")
    method: str = Field("GET", description="HTTP method")
    headers: Optional[Dict[str, str]] = Field(default_factory=dict, description="Request headers")
    body: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Request body")
    
    class Config:
        json_schema_extra = {
            "example": {
                "key_id": "12345678-1234-1234-1234-123456789abc",
                "target_url": "https://api.openai.com/v1/chat/completions",
                "method": "POST",
                "headers": {"Content-Type": "application/json"},
                "body": {
                    "model": "gpt-3.5-turbo",
                    "messages": [{"role": "user", "content": "Hello!"}]
                }
            }
        }


class ProxyCallResponse(BaseModel):
    success: bool
    status_code: Optional[int] = None
    headers: Optional[Dict[str, str]] = None
    data: Optional[Any] = None
    response_time_ms: Optional[float] = None
    error: Optional[str] = None


class ListLogsRequest(BaseModel):
    key_id: str = Field(..., description="ID of the key to get logs for")
    filters: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Log filters")
    
    class Config:
        json_schema_extra = {
            "example": {
                "key_id": "12345678-1234-1234-1234-123456789abc",
                "filters": {
                    "limit": 50,
                    "start_date": "2024-01-01T00:00:00",
                    "caller_id": "coral_agent_bob_session_456"
                }
            }
        }


class ListLogsResponse(BaseModel):
    success: bool
    logs: List[Dict[str, Any]]
    count: int


class ErrorResponse(BaseModel):
    success: bool = False
    error: str
    details: Optional[Dict[str, Any]] = None


# Dependency to get Coral session ID from headers
async def get_coral_session(
    x_coral_session: Optional[str] = Header(None, alias="X-Coral-Session"),
    authorization: Optional[str] = Header(None)
) -> str:
    """Extract Coral session ID from headers"""
    
    # Try X-Coral-Session header first
    if x_coral_session:
        return x_coral_session
    
    # Try Authorization header (Bearer token format)
    if authorization and authorization.startswith("Bearer "):
        return authorization[7:]  # Remove "Bearer " prefix
    
    # Default for testing/demo
    if not x_coral_session and not authorization:
        return "coral_demo_session_default"
    
    raise HTTPException(
        status_code=401,
        detail="Missing Coral session ID. Provide X-Coral-Session header or Authorization Bearer token."
    )


# Startup and shutdown events
@app.on_event("startup")
async def startup_event():
    """Initialize Sage MCP on startup"""
    global sage_instance
    sage_instance = SageMCP()
    logger.info("Sage MCP API service started successfully")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    global sage_instance
    if sage_instance:
        await sage_instance.close()
        logger.info("Sage MCP API service shut down successfully")


# Health check endpoint
@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


# UI Endpoints - Keep minimal for API testing only
@app.get("/ui", tags=["UI"])
async def serve_ui():
    """Basic UI endpoint for API testing"""
    return {"message": "Sage API is running", "ui_location": "Serve frontend separately on port 8080"}

# MCP-specific endpoints (no auth required for MCP protocol)
@app.post("/mcp/add_key", response_model=AddKeyResponse, tags=["MCP"])
async def mcp_add_key(request: AddKeyRequest):
    """MCP: Store a new API key securely"""
    try:
        key_id = await sage_instance.add_key(
            key_name=request.key_name,
            api_key=request.api_key,
            owner_session="mcp_session"  # Use default session for MCP
        )
        return AddKeyResponse(
            success=True,
            key_id=key_id,
            message=f"Key '{request.key_name}' stored successfully"
        )
    except Exception as e:
        logger.error(f"Error adding key via MCP: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/mcp/health", tags=["MCP"])
async def mcp_health_check():
    """MCP: Health check endpoint"""
    return {"status": "healthy", "service": "sage_mcp", "timestamp": datetime.utcnow().isoformat()}


# UI-specific models for better frontend integration
class UIKeyCreate(BaseModel):
    key_name: str = Field(..., description="Human-readable name for the API key")
    api_key: str = Field(..., description="The API key to store securely")
    environment: str = Field(..., description="Environment (staging or prod)")

class UIKeyResponse(BaseModel):
    key_id: str
    key_name: str
    environment: str
    created_at: datetime
    is_active: bool
    grant_count: int

class UIGrantCreate(BaseModel):
    key_id: str = Field(..., description="ID of the key to grant access to")
    caller_agent_id: str = Field(..., description="Agent/App ID that will use this key")
    max_calls_per_day: int = Field(..., description="Maximum calls per day")
    expiry_date: str = Field(..., description="Grant expiry date (YYYY-MM-DD)")

class UIGrantResponse(BaseModel):
    grant_id: str
    key_id: str
    key_name: str
    caller_id: str
    max_calls_per_day: int
    current_usage: int
    expires_at: datetime
    created_at: datetime
    is_active: bool

# API v1 Endpoints for UI
@app.post("/api/v1/keys", response_model=UIKeyResponse, tags=["UI API"])
async def ui_add_key(request: UIKeyCreate):
    """UI: Add a new API key"""
    try:
        # Use a default session for UI operations
        coral_session = "coral_ui_session_default"
        
        key_id = await sage_instance.add_key(
            key_name=request.key_name,
            api_key=request.api_key,
            owner_session=coral_session
        )
        
        return UIKeyResponse(
            key_id=key_id,
            key_name=request.key_name,
            environment=request.environment,
            created_at=datetime.utcnow(),
            is_active=True,
            grant_count=0
        )
        
    except Exception as e:
        logger.error(f"Error adding key via UI: {e}")
        raise HTTPException(status_code=422, detail=str(e))


@app.get("/api/v1/keys", response_model=List[UIKeyResponse], tags=["UI API"])
async def ui_list_keys():
    """UI: List all keys"""
    try:
        coral_session = "coral_ui_session_default"
        keys = await sage_instance.list_keys(coral_session)
        
        # Get grants to calculate grant counts per key
        grants_data = []
        try:
            # Mock grants data for now - in a real implementation, this would come from the database
            # For now, we'll calculate based on mock data or return 0
            pass
        except Exception:
            pass
        
        # Transform to UI format
        ui_keys = []
        for key in keys:
            # Parse the created_at timestamp
            created_at_str = key.get("created_at", datetime.utcnow().isoformat())
            try:
                if created_at_str.endswith('Z'):
                    created_at = datetime.fromisoformat(created_at_str[:-1])
                else:
                    created_at = datetime.fromisoformat(created_at_str)
            except ValueError:
                created_at = datetime.utcnow()
            
            # Calculate grant count for this key (mock implementation)
            grant_count = 0
            # In a real implementation, you would query the grants for this key_id
            # For now, we'll let the frontend handle the count calculation
            
            ui_keys.append(UIKeyResponse(
                key_id=key.get("key_id", ""),
                key_name=key.get("key_name", ""),
                environment="prod",  # Default to prod since backend doesn't store environment yet
                created_at=created_at,
                is_active=key.get("is_active", True),
                grant_count=grant_count
            ))
        
        return ui_keys
        
    except Exception as e:
        logger.error(f"Error listing keys via UI: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/api/v1/keys/{key_id}", tags=["UI API"])
async def ui_delete_key(key_id: str):
    """UI: Delete a key"""
    try:
        coral_session = "coral_ui_session_default"
        success = await sage_instance.revoke_key(key_id, coral_session)
        
        if success:
            return {"success": True, "message": "Key deleted successfully"}
        else:
            raise HTTPException(status_code=404, detail="Key not found")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting key via UI: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/v1/grants", response_model=List[UIGrantResponse], tags=["UI API"])
async def ui_list_grants(key_id: Optional[str] = None):
    """UI: List all grants, optionally filtered by key_id"""
    try:
        coral_session = "coral_ui_session_default"
        
        # For now, return mock data since the backend doesn't have grants implemented yet
        # TODO: Implement actual grants listing in SageMCP
        mock_grants = []
        
        # If we have keys, we can create some mock grants for testing
        try:
            keys = await sage_instance.list_keys(coral_session)
            for i, key in enumerate(keys[:2]):  # Create mock grants for first 2 keys
                mock_grants.append(UIGrantResponse(
                    grant_id=f"grant_{i+1}_{key.get('key_id', '')[:8]}",
                    key_id=key.get('key_id', ''),
                    key_name=key.get('key_name', ''),
                    caller_id=f"test_agent_{i+1}",
                    max_calls_per_day=100 * (i + 1),
                    current_usage=25 * (i + 1),
                    expires_at=datetime.utcnow().replace(day=datetime.utcnow().day + 7 + i),
                    created_at=datetime.utcnow().replace(day=datetime.utcnow().day - i),
                    is_active=True
                ))
        except Exception:
            pass  # If no keys, return empty list
        
        # Filter by key_id if provided
        if key_id:
            mock_grants = [g for g in mock_grants if g.key_id == key_id]
        
        return mock_grants
        
    except Exception as e:
        logger.error(f"Error listing grants via UI: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/v1/grants", response_model=UIGrantResponse, tags=["UI API"])
async def ui_create_grant(request: UIGrantCreate):
    """UI: Create a new access grant"""
    try:
        coral_session = "coral_ui_session_default"
        
        # Parse expiry date
        from datetime import datetime
        try:
            expiry_date = datetime.fromisoformat(request.expiry_date)
        except ValueError:
            raise HTTPException(status_code=422, detail="Invalid expiry date format. Use YYYY-MM-DD")
        
        # Calculate expiry hours from now
        expiry_hours = int((expiry_date - datetime.utcnow()).total_seconds() / 3600)
        if expiry_hours <= 0:
            raise HTTPException(status_code=422, detail="Expiry date must be in the future")
        
        # Create grant using existing grant_access method
        success = await sage_instance.grant_access(
            key_id=request.key_id,
            caller_id=request.caller_agent_id,
            permissions={"max_calls_per_day": request.max_calls_per_day},
            expiry=expiry_hours,
            owner_session=coral_session
        )
        
        if not success:
            raise HTTPException(status_code=400, detail="Failed to create grant")
        
        # Get key name for response
        key_name = "Unknown Key"
        try:
            keys = await sage_instance.list_keys(coral_session)
            for key in keys:
                if key.get('key_id') == request.key_id:
                    key_name = key.get('key_name', 'Unknown Key')
                    break
        except Exception:
            pass
        
        # Return the created grant
        grant_id = f"grant_{datetime.utcnow().timestamp()}_{request.key_id[:8]}"
        
        return UIGrantResponse(
            grant_id=grant_id,
            key_id=request.key_id,
            key_name=key_name,
            caller_id=request.caller_agent_id,
            max_calls_per_day=request.max_calls_per_day,
            current_usage=0,
            expires_at=expiry_date,
            created_at=datetime.utcnow(),
            is_active=True
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating grant via UI: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/api/v1/grants/{grant_id}", tags=["UI API"])
async def ui_revoke_grant(grant_id: str):
    """UI: Revoke an access grant"""
    try:
        coral_session = "coral_ui_session_default"
        
        # For now, just return success since we don't have grant revocation implemented
        # TODO: Implement actual grant revocation in SageMCP
        logger.info(f"Revoking grant {grant_id} for session {coral_session}")
        
        return {"success": True, "message": "Grant revoked successfully"}
        
    except Exception as e:
        logger.error(f"Error revoking grant via UI: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/v1/logs", tags=["UI API"])
async def ui_get_logs(key_id: Optional[str] = None, time_filter: str = "24h"):
    """UI: Get usage logs"""
    try:
        coral_session = "coral_ui_session_default"
        
        # For now, return mock data since logs aren't fully implemented
        # TODO: Implement actual logs retrieval
        mock_logs = []
        
        # Create some mock log entries
        for i in range(5):
            mock_logs.append({
                "log_id": f"log_{i+1}",
                "key_id": key_id or f"key_{i+1}",
                "caller_id": f"agent_{i+1}",
                "action": "proxy_call",
                "target_url": "https://api.openai.com/v1/chat/completions",
                "status_code": 200,
                "response_time": 1200 + (i * 100),
                "timestamp": datetime.utcnow().replace(hour=datetime.utcnow().hour - i),
                "success": True
            })
        
        return {"success": True, "logs": mock_logs, "count": len(mock_logs)}
        
    except Exception as e:
        logger.error(f"Error getting logs via UI: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# Original API Key Management Endpoints (keep for backward compatibility)
@app.post("/keys", response_model=AddKeyResponse, tags=["Key Management"])
async def add_key(
    request: AddKeyRequest,
    coral_session: str = Depends(get_coral_session)
):
    """
    Store a new API key securely
    
    - **key_name**: Human-readable name for the key
    - **api_key**: The actual API key to encrypt and store
    """
    try:
        key_id = await sage_instance.add_key(
            key_name=request.key_name,
            api_key=request.api_key,
            owner_session=coral_session
        )
        
        return AddKeyResponse(
            success=True,
            key_id=key_id,
            message=f"Key '{request.key_name}' stored successfully"
        )
        
    except Exception as e:
        logger.error(f"Error adding key: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/keys", tags=["Key Management"])
async def list_keys(coral_session: str = Depends(get_coral_session)):
    """List all keys for the authenticated user (metadata only)"""
    try:
        keys = await sage_instance.list_keys(coral_session)
        return {"success": True, "keys": keys, "count": len(keys)}
        
    except Exception as e:
        logger.error(f"Error listing keys: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/keys/{key_id}", tags=["Key Management"])
async def revoke_key(
    key_id: str,
    coral_session: str = Depends(get_coral_session)
):
    """Revoke a key and all associated grants"""
    try:
        success = await sage_instance.revoke_key(key_id, coral_session)
        
        if success:
            return {"success": True, "message": "Key revoked successfully"}
        else:
            raise HTTPException(status_code=404, detail="Key not found or access denied")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error revoking key: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# Access Grant Management Endpoints
@app.post("/grants", response_model=GrantAccessResponse, tags=["Access Management"])
async def grant_access(
    request: GrantAccessRequest,
    coral_session: str = Depends(get_coral_session)
):
    """
    Grant access to an API key for another agent
    
    - **key_id**: ID of the key to grant access to
    - **caller_id**: Coral session ID of the agent receiving access
    - **permissions**: Permission settings (e.g., max_calls_per_day)
    - **expiry_hours**: Grant expiry in hours
    """
    try:
        success = await sage_instance.grant_access(
            key_id=request.key_id,
            caller_id=request.caller_id,
            permissions=request.permissions,
            expiry=request.expiry_hours,
            owner_session=coral_session
        )
        
        if success:
            return GrantAccessResponse(
                success=True,
                message="Access granted successfully"
            )
        else:
            raise HTTPException(status_code=400, detail="Failed to grant access")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error granting access: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# Proxy Call Endpoint
@app.post("/proxy", response_model=ProxyCallResponse, tags=["Proxy Calls"])
async def proxy_call(
    request: ProxyCallRequest,
    coral_session: str = Depends(get_coral_session)
):
    """
    Make a proxied API call using a stored key
    
    - **key_id**: ID of the key to use for the API call
    - **target_url**: Target API URL
    - **method**: HTTP method (GET, POST, etc.)
    - **headers**: Request headers
    - **body**: Request body
    """
    try:
        response = await sage_instance.proxy_call(
            key_id=request.key_id,
            target_url=request.target_url,
            payload={
                "method": request.method,
                "headers": request.headers,
                "body": request.body
            },
            caller_session=coral_session
        )
        
        return ProxyCallResponse(
            success=response.get("success", True),
            status_code=response.get("status_code"),
            headers=response.get("headers"),
            data=response.get("data"),
            response_time_ms=response.get("response_time_ms")
        )
        
    except Exception as e:
        logger.error(f"Error in proxy call: {e}")
        return ProxyCallResponse(
            success=False,
            error=str(e)
        )


# Audit and Logging Endpoints
@app.post("/logs", response_model=ListLogsResponse, tags=["Audit & Logging"])
async def list_logs(
    request: ListLogsRequest,
    coral_session: str = Depends(get_coral_session)
):
    """
    Get audit logs for a specific key
    
    - **key_id**: ID of the key to get logs for
    - **filters**: Optional filters (limit, start_date, end_date, caller_id, action)
    """
    try:
        logs = await sage_instance.list_logs(
            key_id=request.key_id,
            filters=request.filters,
            owner_session=coral_session
        )
        
        return ListLogsResponse(
            success=True,
            logs=logs,
            count=len(logs)
        )
        
    except Exception as e:
        logger.error(f"Error listing logs: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/stats/{key_id}", tags=["Audit & Logging"])
async def get_usage_stats(
    key_id: str,
    days: int = 7,
    coral_session: str = Depends(get_coral_session)
):
    """Get usage statistics for a key"""
    try:
        stats = await sage_instance.get_usage_stats(
            key_id=key_id,
            owner_session=coral_session,
            days=days
        )
        
        return {"success": True, "stats": stats}
        
    except Exception as e:
        logger.error(f"Error getting usage stats: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# MCP Protocol Endpoint (for direct MCP integration)
@app.post("/mcp", tags=["MCP Protocol"])
async def handle_mcp_request(request: Dict[str, Any]):
    """
    Handle MCP protocol requests directly
    
    This endpoint accepts MCP-formatted requests and returns MCP-formatted responses.
    Useful for direct MCP integration or testing.
    """
    try:
        response = await sage_instance.handle_mcp_request(request)
        return response
        
    except Exception as e:
        logger.error(f"Error handling MCP request: {e}")
        return {
            "success": False,
            "error": {
                "error_code": "INTERNAL_ERROR",
                "error_message": str(e),
                "coral_session_id": request.get("session_id", "")
            }
        }


# Admin/Maintenance Endpoints
@app.post("/admin/cleanup", tags=["Administration"])
async def cleanup_expired_grants():
    """Cleanup expired grants (admin operation)"""
    try:
        count = await sage_instance.cleanup_expired_grants()
        return {"success": True, "cleaned_grants": count}
        
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Custom HTTP exception handler"""
    return JSONResponse(
        status_code=exc.status_code,
        content={"success": False, "error": exc.detail}
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """General exception handler"""
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"success": False, "error": "Internal server error"}
    )


if __name__ == "__main__":
    import uvicorn
    
    # Run the FastAPI server
    uvicorn.run(
        "sage_api:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
        log_level="info"
    )