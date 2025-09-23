#!/usr/bin/env python3
"""
Sage MCP FastAPI Service

This FastAPI service exposes Sage MCP functionality as REST endpoints.
It can be used directly or wrapped as an MCP server for Coral integration.
"""

from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
import asyncio
import logging
from datetime import datetime

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
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
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


# API Key Management Endpoints
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
        port=8000,
        reload=True,
        log_level="info"
    )