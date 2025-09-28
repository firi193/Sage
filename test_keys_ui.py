#!/usr/bin/env python3
"""
Test script for Keys UI functionality
"""

import asyncio
import json
from sage.sage_mcp import SageMCP

async def test_keys_functionality():
    """Test the keys management functionality"""
    print("🧪 Testing Keys Management Functionality")
    
    # Initialize SageMCP
    sage = SageMCP()
    
    try:
        # Test adding a key
        print("\n1. Testing add_key...")
        key_id = await sage.add_key(
            key_name="Test OpenAI Key",
            api_key="sk-test123456789",
            owner_session="coral_ui_session_default"
        )
        print(f"✅ Key added successfully: {key_id}")
        
        # Test listing keys
        print("\n2. Testing list_keys...")
        keys = await sage.list_keys("coral_ui_session_default")
        print(f"✅ Found {len(keys)} keys:")
        for key in keys:
            print(f"   - {key['key_name']} ({key['key_id']})")
        
        # Test key data structure
        if keys:
            print("\n3. Key data structure:")
            print(json.dumps(keys[0], indent=2, default=str))
        
        print("\n✅ All tests passed!")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Cleanup
        await sage.close()

if __name__ == "__main__":
    asyncio.run(test_keys_functionality())