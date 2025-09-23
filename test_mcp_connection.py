#!/usr/bin/env python3
"""
Test MCP Connection - Simple test to debug MCP client issues
"""

import asyncio
import json
import aiohttp
from langchain_mcp_adapters.client import MultiServerMCPClient

async def test_mcp_connection():
    """Test MCP connection and tool discovery"""
    
    print("🔍 Testing MCP Connection...")
    
    # Test 1: Direct HTTP call to tools endpoint
    print("\n1️⃣ Testing direct HTTP call to tools endpoint...")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("http://172.30.208.1:8002/mcp/tools") as response:
                tools_data = await response.json()
                print(f"✅ Direct HTTP call successful: {len(tools_data['tools'])} tools found")
                for tool in tools_data['tools']:
                    print(f"   - {tool['name']}: {tool['description']}")
    except Exception as e:
        print(f"❌ Direct HTTP call failed: {e}")
        return
    
    # Test 2: MCP Client connection
    print("\n2️⃣ Testing MCP Client connection...")
    try:
        client = MultiServerMCPClient(
            connections={
                "sage_mcp": {
                    "transport": "sse",
                    "url": "http://172.30.208.1:8002/sse",
                    "description": "Sage API Key Management and Proxy Service"
                }
            }
        )
        
        print("✅ MCP Client created successfully")
        
        # Test 3: Get tools via MCP client
        print("\n3️⃣ Testing tool discovery via MCP client...")
        
        try:
            # Try async first
            tools = await client.get_tools()
            print(f"✅ Async get_tools successful: {len(tools)} tools")
        except TypeError:
            # Try sync
            print("⚠️ Async failed, trying sync...")
            tools = client.get_tools()
            print(f"✅ Sync get_tools successful: {len(tools)} tools")
        except Exception as e:
            print(f"❌ get_tools failed: {e}")
            return
        
        # List tools
        if tools:
            print("\n📋 Tools discovered via MCP client:")
            for tool in tools:
                print(f"   - {tool.name}: {tool.description}")
        else:
            print("⚠️ No tools discovered via MCP client")
            
    except Exception as e:
        print(f"❌ MCP Client connection failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_mcp_connection())