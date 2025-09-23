#!/usr/bin/env python3
"""
MCP Tools Client - Properly connects to MCP server to get available tools
"""

import json
import requests
import uuid

def get_mcp_tools():
    """Get tools from MCP server using proper MCP protocol"""
    
    mcp_url = "http://localhost:8001/mcp"  # Updated to port 8001
    
    # MCP protocol message to list tools
    mcp_request = {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": "tools/list",
        "params": {}
    }
    
    # Headers for SSE connection
    headers = {
        "Accept": "text/event-stream",
        "Content-Type": "application/json",
        "Cache-Control": "no-cache"
    }
    
    try:
        print("🔌 Connecting to MCP server...")
        
        # Make SSE connection
        response = requests.post(
            mcp_url,
            json=mcp_request,
            headers=headers,
            stream=True,
            timeout=10
        )
        
        print(f"📡 Response status: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ Connected! Reading tools...")
            
            # Read SSE stream
            for line in response.iter_lines(decode_unicode=True):
                if line.startswith("data: "):
                    data = line[6:]  # Remove "data: " prefix
                    try:
                        mcp_response = json.loads(data)
                        
                        if "result" in mcp_response:
                            tools = mcp_response["result"].get("tools", [])
                            print(f"\n🛠️  Found {len(tools)} MCP tools:")
                            print("=" * 50)
                            
                            for i, tool in enumerate(tools, 1):
                                print(f"{i}. {tool['name']}")
                                print(f"   Description: {tool.get('description', 'No description')}")
                                
                                # Show input schema
                                schema = tool.get('inputSchema', {})
                                properties = schema.get('properties', {})
                                if properties:
                                    print(f"   Parameters: {', '.join(properties.keys())}")
                                print()
                            
                            return tools
                        
                        elif "error" in mcp_response:
                            print(f"❌ MCP Error: {mcp_response['error']}")
                            return None
                            
                    except json.JSONDecodeError:
                        continue
        else:
            print(f"❌ Failed to connect: {response.status_code}")
            print(f"Response: {response.text}")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def get_tools_via_openapi():
    """Alternative: Get tools by inspecting OpenAPI spec"""
    
    print("\n🔍 Alternative: Getting tools from OpenAPI spec...")
    
    try:
        response = requests.get("http://localhost:8001/openapi.json")  # Updated to port 8001
        
        if response.status_code == 200:
            openapi_spec = response.json()
            paths = openapi_spec.get("paths", {})
            
            print(f"📋 Found {len(paths)} API endpoints that could be MCP tools:")
            print("=" * 50)
            
            for path, methods in paths.items():
                for method, details in methods.items():
                    if method.upper() == "POST":  # MCP tools are typically POST
                        summary = details.get("summary", "No description")
                        print(f"• {method.upper()} {path}")
                        print(f"  {summary}")
                        
                        # Show parameters
                        request_body = details.get("requestBody", {})
                        if request_body:
                            content = request_body.get("content", {})
                            json_content = content.get("application/json", {})
                            schema = json_content.get("schema", {})
                            
                            if "$ref" in schema:
                                ref_name = schema["$ref"].split("/")[-1]
                                print(f"  Parameters: {ref_name} schema")
                            elif "properties" in schema:
                                props = schema["properties"].keys()
                                print(f"  Parameters: {', '.join(props)}")
                        print()
            
        else:
            print(f"❌ Could not get OpenAPI spec: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error getting OpenAPI spec: {e}")

if __name__ == "__main__":
    print("🚀 Sage MCP Tools Discovery")
    print("=" * 50)
    
    # Try MCP protocol first
    tools = get_mcp_tools()
    
    # If that fails, try OpenAPI inspection
    if not tools:
        get_tools_via_openapi()
    
    print("\n💡 Note: The MCP endpoint uses Server-Sent Events (SSE)")
    print("   It's designed for MCP clients, not direct browser access.")
    print("   Use this script or an MCP client to interact with it.")