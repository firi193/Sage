#!/usr/bin/env python3
"""
Simple Sage MCP Server - Clean implementation without deprecation warnings
"""

from fastapi import FastAPI
from fastapi_mcp import FastApiMCP
import uvicorn
import sys
import os

# Add current directory to path to import sage_api
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def create_app():
    """Create the FastAPI app with MCP integration"""
    
    # Import the sage app
    from sage_api import app as sage_app
    
    # Create MCP wrapper
    mcp = FastApiMCP(sage_app)
    
    # Mount using HTTP transport (recommended)
    mcp.mount_http()
    
    return sage_app

# Create the app instance
app = create_app()

if __name__ == "__main__":
    print("🚀 Starting Sage MCP Server...")
    print("📡 FastAPI REST API: http://localhost:8000")
    print("🔌 MCP Protocol: http://localhost:8000/mcp")
    print("📖 API Docs: http://localhost:8000/docs")
    print("🔍 MCP Tools: http://localhost:8000/mcp/tools")
    print("\n✨ Server starting...")
    
    # Run with uvicorn
    uvicorn.run(
        "sage_mcp_simple:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info"
    )