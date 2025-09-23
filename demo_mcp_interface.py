#!/usr/bin/env python3
"""
Demonstration script for Sage MCP Interface
Shows how to use the MCP interface for key management and proxy calls
"""

import asyncio
import json
from sage.services.mcp_interface import MCPInterface


async def demo_mcp_interface():
    """Demonstrate MCP interface functionality"""
    
    print("🚀 Sage MCP Interface Demo")
    print("=" * 50)
    
    # Create MCP interface
    mcp = MCPInterface()
    
    # Demo 1: Add API Key
    print("\n1. Adding API Key...")
    import time
    unique_suffix = str(int(time.time()))
    add_key_request = {
        "method": "add_key",
        "session_id": "coral_session_owner_123",
        "params": {
            "key_name": f"openai_demo_key_{unique_suffix}",
            "api_key": "sk-demo123456789"
        }
    }
    
    try:
        result = await mcp.handle_mcp_request(add_key_request)
        print(f"✅ Add Key Result: {json.dumps(result, indent=2)}")
        
        if result["success"]:
            key_id = result["data"]["key_id"]
            print(f"📝 Generated Key ID: {key_id}")
        else:
            print("❌ Failed to add key")
            return
            
    except Exception as e:
        print(f"❌ Error adding key: {e}")
        return
    
    # Demo 2: Grant Access
    print("\n2. Granting Access to Another Agent...")
    grant_request = {
        "method": "grant_access",
        "session_id": "coral_session_owner_123",
        "params": {
            "key_id": key_id,
            "caller_id": "coral_agent_caller_456",
            "permissions": {"max_calls_per_day": 50},
            "expiry_hours": 24
        }
    }
    
    try:
        result = await mcp.handle_mcp_request(grant_request)
        print(f"✅ Grant Access Result: {json.dumps(result, indent=2)}")
        
        if not result["success"]:
            print("❌ Failed to grant access")
            return
            
    except Exception as e:
        print(f"❌ Error granting access: {e}")
        return
    
    # Demo 3: Attempt Proxy Call (will fail due to mocked services)
    print("\n3. Attempting Proxy Call...")
    proxy_request = {
        "method": "proxy_call",
        "session_id": "coral_agent_caller_456",
        "params": {
            "key_id": key_id,
            "target_url": "https://api.openai.com/v1/chat/completions",
            "method": "POST",
            "headers": {"Content-Type": "application/json"},
            "payload": {
                "model": "gpt-3.5-turbo",
                "messages": [{"role": "user", "content": "Hello, world!"}],
                "max_tokens": 50
            }
        }
    }
    
    try:
        result = await mcp.handle_mcp_request(proxy_request)
        print(f"📡 Proxy Call Result: {json.dumps(result, indent=2)}")
        
        if result["success"]:
            print("✅ Proxy call successful!")
        else:
            print(f"⚠️  Proxy call failed: {result['error']['error_message']}")
            
    except Exception as e:
        print(f"❌ Error in proxy call: {e}")
    
    # Demo 4: List Logs
    print("\n4. Listing Logs...")
    logs_request = {
        "method": "list_logs",
        "session_id": "coral_session_owner_123",
        "params": {
            "key_id": key_id,
            "filters": {}
        }
    }
    
    try:
        result = await mcp.handle_mcp_request(logs_request)
        print(f"📋 List Logs Result: {json.dumps(result, indent=2)}")
        
        if result["success"]:
            print(f"✅ Found {len(result['data']['logs'])} log entries")
        else:
            print(f"⚠️  Failed to list logs: {result['error']['error_message']}")
            
    except Exception as e:
        print(f"❌ Error listing logs: {e}")
    
    # Demo 5: Session Validation
    print("\n5. Testing Session Validation...")
    
    try:
        # Valid session
        caller_id = await mcp.validate_coral_session("coral_session_123")
        print(f"✅ Valid session validated: {caller_id}")
        
        # Valid session with wallet
        caller_id = await mcp.validate_coral_session("coral_session_123", "wallet_456")
        print(f"✅ Valid session with wallet validated: {caller_id}")
        
        # Invalid session
        try:
            await mcp.validate_coral_session("invalid_session")
            print("❌ Should have failed validation")
        except ValueError as e:
            print(f"✅ Invalid session properly rejected: {e}")
            
    except Exception as e:
        print(f"❌ Error in session validation: {e}")
    
    # Cleanup
    await mcp.proxy_service.close()
    
    print("\n🎉 Demo completed!")
    print("\nKey Features Demonstrated:")
    print("- ✅ MCP protocol compliance")
    print("- ✅ Coral session validation")
    print("- ✅ API key storage and management")
    print("- ✅ Access grant creation")
    print("- ✅ Proxy call handling (with integrated HTTP client)")
    print("- ✅ Comprehensive error handling")
    print("- ✅ Privacy-aware logging")


if __name__ == "__main__":
    asyncio.run(demo_mcp_interface())