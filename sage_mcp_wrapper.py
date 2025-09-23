#!/usr/bin/env python3
"""
Sage MCP Wrapper - Converts FastAPI service to MCP server for Coral integration

This file wraps the sage_api.py FastAPI service using fastapi-mcp to make it
compatible with the MCP protocol and Coral agents.
"""

from fastapi import FastAPI
from fastapi_mcp import FastApiMCP
import uvicorn

# Import your existing FastAPI app
from sage_api import app as sage_app

def create_mcp_server():
    """Create and configure the MCP server wrapper"""
    
    # Create the MCP wrapper for your FastAPI app
    mcp = FastApiMCP(sage_app)
    
    # Mount the MCP server directly to your FastAPI app
    # This makes MCP available at http://localhost:8001/mcp
    mcp.mount()
    
    return sage_app

def main():
    """Main function to run the MCP-wrapped FastAPI server"""
    
    # Create the MCP-enabled app
    app = create_mcp_server()
    
    print("🚀 Starting Sage MCP Server...")
    print("📡 FastAPI endpoints available at: http://localhost:8001")
    print("🔌 MCP protocol available at: http://localhost:8001/mcp")
    print("📖 API documentation at: http://localhost:8001/docs")
    print("🔍 MCP tools documentation at: http://localhost:8001/mcp/tools")
    
    # Run the server without reload to avoid the warning
    # Use the module string format for reload compatibility
    uvicorn.run(
        "sage_mcp_wrapper:create_mcp_server",
        host="0.0.0.0",
        port=8001,  # Changed to 8001 to avoid conflicts
        reload=False,  # Disable reload to avoid import string warning
        log_level="info",
        factory=True  # Tell uvicorn this is a factory function
    )

if __name__ == "__main__":
    main()