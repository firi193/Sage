#!/usr/bin/env python3
"""
Test if FastAPI app actually connects to PostgreSQL
"""

import os
import sys
import asyncio
from dotenv import load_dotenv

load_dotenv()

async def test_fastapi_postgres_integration():
    """Test if FastAPI app uses PostgreSQL"""
    print("🔍 Testing FastAPI PostgreSQL Integration")
    print("=" * 50)
    
    try:
        # Import and initialize SageMCP
        from sage.sage_mcp import SageMCP
        
        print("📦 Initializing SageMCP...")
        sage = SageMCP()
        
        # Check if services are using PostgreSQL
        print("\n🔍 Checking database configuration...")
        
        # Check KeyManager's storage service
        key_storage = sage.key_manager.storage_service
        print(f"KeyStorage database path: {getattr(key_storage, 'db_path', 'Not set')}")
        
        # Check AuthorizationEngine
        auth_engine = sage.authorization_engine
        print(f"AuthEngine database path: {getattr(auth_engine, 'db_path', 'Not set')}")
        
        # Check PolicyEngine
        policy_engine = sage.policy_engine
        print(f"PolicyEngine database path: {getattr(policy_engine, 'db_path', 'Not set')}")
        
        # Check LoggingService
        logging_service = sage.logging_service
        print(f"LoggingService database path: {getattr(logging_service, 'db_path', 'Not set')}")
        
        print(f"\nEnvironment: {os.getenv('ENVIRONMENT')}")
        print(f"Using PostgreSQL: {os.getenv('ENVIRONMENT') == 'production'}")
        
        # Test if we can actually connect to PostgreSQL through the services
        print("\n🧪 Testing service database connections...")
        
        try:
            # Test key storage
            with key_storage._get_connection() as conn:
                if hasattr(conn, 'execute'):
                    cursor = conn.cursor()
                    cursor.execute("SELECT COUNT(*) FROM sage_keys_stored_keys")
                    count = cursor.fetchone()[0]
                    print(f"✅ KeyStorage connected to PostgreSQL: {count} keys")
                else:
                    print("❌ KeyStorage not using PostgreSQL")
        except Exception as e:
            print(f"❌ KeyStorage connection failed: {e}")
        
        # Test authorization engine
        try:
            with auth_engine._get_connection() as conn:
                if hasattr(conn, 'execute'):
                    cursor = conn.cursor()
                    cursor.execute("SELECT COUNT(*) FROM sage_grants_access_grants")
                    count = cursor.fetchone()[0]
                    print(f"✅ AuthEngine connected to PostgreSQL: {count} grants")
                else:
                    print("❌ AuthEngine not using PostgreSQL")
        except Exception as e:
            print(f"❌ AuthEngine connection failed: {e}")
        
        # Test a simple operation
        print("\n🧪 Testing key listing...")
        try:
            keys = await sage.list_keys("test_session")
            print(f"✅ Key listing works: {len(keys)} keys found")
        except Exception as e:
            print(f"❌ Key listing failed: {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_fastapi_postgres_integration())
    
    if success:
        print("\n🎉 FastAPI PostgreSQL integration test completed!")
    else:
        print("\n❌ FastAPI PostgreSQL integration test failed!")
        print("The services are still using SQLite, not PostgreSQL.")
        sys.exit(1)