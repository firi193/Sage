#!/usr/bin/env python3
"""
Test script to check MCP endpoints
"""

import requests
import json

def test_endpoints():
    base_url = "http://localhost:8000"
    
    endpoints_to_test = [
        "/health",
        "/docs", 
        "/mcp",
        "/mcp/tools",
        "/mcp/list_tools",
        "/mcp/tools/list"
    ]
    
    print("🔍 Testing Sage MCP Endpoints...")
    print("=" * 50)
    
    for endpoint in endpoints_to_test:
        url = f"{base_url}{endpoint}"
        try:
            response = requests.get(url, timeout=5)
            print(f"✅ {endpoint}: {response.status_code}")
            
            if endpoint == "/mcp" and response.status_code == 200:
                print(f"   Response: {response.text[:100]}...")
                
        except requests.exceptions.RequestException as e:
            print(f"❌ {endpoint}: Error - {e}")
    
    print("\n" + "=" * 50)
    print("🔍 Checking FastAPI docs for all available routes...")
    
    try:
        # Get OpenAPI spec to see all routes
        response = requests.get(f"{base_url}/openapi.json")
        if response.status_code == 200:
            openapi_spec = response.json()
            paths = openapi_spec.get("paths", {})
            
            print(f"📋 Found {len(paths)} API endpoints:")
            for path in sorted(paths.keys()):
                methods = list(paths[path].keys())
                print(f"   {path} ({', '.join(methods).upper()})")
        else:
            print("❌ Could not get OpenAPI spec")
            
    except Exception as e:
        print(f"❌ Error getting API spec: {e}")

if __name__ == "__main__":
    test_endpoints()