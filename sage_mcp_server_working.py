#!/usr/bin/env python3
"""
Working Sage MCP Server - Manual MCP implementation that calls your REST API

This creates a proper MCP server that exposes tools and calls your existing
FastAPI endpoints. This bypasses the fastapi-mcp issues.
"""

import asyncio
import json
import aiohttp
from typing import Dict, Any, List
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
import uvicorn

app = FastAPI(title="Sage MCP Server", version="1.0.0")

# Base URL for your Sage API
SAGE_API_BASE = "http://localhost:8001"

class MCPServer:
    def __init__(self):
        self.tools = [
            {
                "name": "add_key",
                "description": "Store a new API key securely",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "key_name": {"type": "string", "description": "Human-readable name for the API key"},
                        "api_key": {"type": "string", "description": "The API key to store securely"}
                    },
                    "required": ["key_name", "api_key"]
                }
            },
            {
                "name": "health_check",
                "description": "Check system health",
                "inputSchema": {
                    "type": "object",
                    "properties": {}
                }
            },
            {
                "name": "grant_access",
                "description": "Grant access to an API key",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "key_id": {"type": "string", "description": "ID of the key to grant access to"},
                        "caller_id": {"type": "string", "description": "Coral session ID of the agent receiving access"},
                        "permissions": {"type": "object", "description": "Permission settings"},
                        "expiry_hours": {"type": "integer", "description": "Grant expiry in hours", "default": 24}
                    },
                    "required": ["key_id", "caller_id", "permissions"]
                }
            },
            {
                "name": "proxy_call",
                "description": "Make a proxied API call using a stored key",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "key_id": {"type": "string", "description": "ID of the key to use"},
                        "target_url": {"type": "string", "description": "Target API URL"},
                        "method": {"type": "string", "description": "HTTP method", "default": "GET"},
                        "headers": {"type": "object", "description": "Request headers"},
                        "body": {"type": "object", "description": "Request body"}
                    },
                    "required": ["key_id", "target_url"]
                }
            },
            {
                "name": "list_logs",
                "description": "Get audit logs for a key",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "key_id": {"type": "string", "description": "ID of the key to get logs for"},
                        "filters": {"type": "object", "description": "Log filters"}
                    },
                    "required": ["key_id"]
                }
            },
            {
                "name": "cleanup_expired_grants",
                "description": "Cleanup expired grants",
                "inputSchema": {
                    "type": "object",
                    "properties": {}
                }
            }
        ]
    
    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call a tool by making HTTP requests to your Sage API"""
        
        async with aiohttp.ClientSession() as session:
            try:
                if name == "add_key":
                    async with session.post(f"{SAGE_API_BASE}/mcp/add_key", json=arguments) as response:
                        return await response.json()
                
                elif name == "health_check":
                    async with session.get(f"{SAGE_API_BASE}/mcp/health") as response:
                        return await response.json()
                
                elif name == "grant_access":
                    headers = {"X-Coral-Session": "mcp_session"}
                    async with session.post(f"{SAGE_API_BASE}/grants", json=arguments, headers=headers) as response:
                        return await response.json()
                
                elif name == "proxy_call":
                    headers = {"X-Coral-Session": "mcp_session"}
                    async with session.post(f"{SAGE_API_BASE}/proxy", json=arguments, headers=headers) as response:
                        return await response.json()
                
                elif name == "list_logs":
                    headers = {"X-Coral-Session": "mcp_session"}
                    async with session.post(f"{SAGE_API_BASE}/logs", json=arguments, headers=headers) as response:
                        return await response.json()
                
                elif name == "cleanup_expired_grants":
                    async with session.post(f"{SAGE_API_BASE}/admin/cleanup") as response:
                        return await response.json()
                
                else:
                    return {"error": f"Unknown tool: {name}"}
                    
            except Exception as e:
                return {"error": str(e)}

mcp_server = MCPServer()

@app.get("/sse")
async def sse_endpoint():
    """SSE endpoint for MCP protocol"""
    
    async def event_stream():
        # Send MCP initialization
        init_msg = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {}
                },
                "serverInfo": {
                    "name": "sage-mcp-server",
                    "version": "1.0.0"
                }
            }
        }
        yield f"data: {json.dumps(init_msg)}\n\n"
        
        # Send tools list immediately
        tools_msg = {
            "jsonrpc": "2.0",
            "method": "notifications/tools/list_changed",
            "params": {
                "tools": mcp_server.tools
            }
        }
        yield f"data: {json.dumps(tools_msg)}\n\n"
        
        # Keep connection alive
        while True:
            yield f"data: {json.dumps({'type': 'heartbeat', 'timestamp': asyncio.get_event_loop().time()})}\n\n"
            await asyncio.sleep(30)
    
    return StreamingResponse(event_stream(), media_type="text/event-stream")

@app.post("/mcp")
async def handle_mcp_request(request: Dict[str, Any]):
    """Handle MCP protocol requests"""
    
    method = request.get("method")
    params = request.get("params", {})
    request_id = request.get("id")
    
    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "tools": mcp_server.tools
            }
        }
    
    elif method == "tools/call":
        tool_name = params.get("name")
        arguments = params.get("arguments", {})
        
        result = await mcp_server.call_tool(tool_name, arguments)
        
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(result, indent=2)
                    }
                ]
            }
        }
    
    else:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {
                "code": -32601,
                "message": f"Method not found: {method}"
            }
        }

@app.get("/mcp/tools")
async def list_tools():
    """List available MCP tools"""
    return {"tools": mcp_server.tools}

@app.get("/health")
async def health():
    """Health check"""
    return {"status": "healthy", "service": "sage_mcp_server"}

if __name__ == "__main__":
    print("🚀 Starting Working Sage MCP Server...")
    print("📡 MCP Server available at: http://localhost:8002")
    print("🔌 SSE endpoint: http://localhost:8002/sse")
    print("🛠️ Tools endpoint: http://localhost:8002/mcp/tools")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8002,  # Different port to avoid conflicts
        log_level="info"
    )