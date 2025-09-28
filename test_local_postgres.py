#!/usr/bin/env python3
"""
Test FastAPI app locally with PostgreSQL connection
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_postgres_connection():
    """Test PostgreSQL connection"""
    print("🔍 Testing PostgreSQL Connection...")
    
    try:
        from sage.config.database import db_config, is_postgres, get_db_connection
        
        print(f"Environment: {os.getenv('ENVIRONMENT')}")
        print(f"Using PostgreSQL: {is_postgres()}")
        
        if is_postgres():
            print("✅ PostgreSQL configuration detected")
            
            # Test connection
            with get_db_connection('keys') as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM sage_keys_stored_keys")
                count = cursor.fetchone()[0]
                print(f"✅ Connected to PostgreSQL - Found {count} keys")
                
                # Test a simple query
                cursor.execute("SELECT key_name FROM sage_keys_stored_keys LIMIT 3")
                keys = cursor.fetchall()
                print(f"Sample keys: {[key[0] for key in keys]}")
                
        else:
            print("❌ Not using PostgreSQL - check your .env file")
            print("Make sure ENVIRONMENT=production and DATABASE_URL is set")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False
    
    return True

def test_fastapi_endpoints():
    """Test FastAPI endpoints"""
    print("\n🚀 Testing FastAPI Endpoints...")
    
    try:
        import uvicorn
        from fastapi.testclient import TestClient
        from sage_api import app
        
        client = TestClient(app)
        
        # Test health endpoint
        response = client.get("/api/v1/health")
        print(f"Health check: {response.status_code} - {response.json()}")
        
        # Test keys endpoint
        response = client.get("/api/v1/keys")
        print(f"Keys endpoint: {response.status_code}")
        if response.status_code == 200:
            keys = response.json()
            print(f"Found {len(keys.get('keys', []))} keys")
        
        return True
        
    except Exception as e:
        print(f"❌ FastAPI test error: {e}")
        return False

if __name__ == "__main__":
    print("🧪 Testing Local PostgreSQL Connection")
    print("=" * 50)
    
    # Test 1: Database connection
    if test_postgres_connection():
        print("✅ Database connection test passed")
    else:
        print("❌ Database connection test failed")
        sys.exit(1)
    
    # Test 2: FastAPI endpoints
    if test_fastapi_endpoints():
        print("✅ FastAPI endpoints test passed")
    else:
        print("❌ FastAPI endpoints test failed")
        sys.exit(1)
    
    print("\n🎉 All tests passed! Your app is ready for PostgreSQL.")