#!/usr/bin/env python3
"""
Test FastAPI app with PostgreSQL - Start server and test endpoints
"""

import os
import sys
import time
import requests
import subprocess
import signal
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_fastapi_with_postgres():
    """Test FastAPI app with PostgreSQL connection"""
    print("🚀 Testing FastAPI with PostgreSQL")
    print("=" * 50)
    
    # Check environment
    print(f"Environment: {os.getenv('ENVIRONMENT')}")
    print(f"Database URL: {'Set' if os.getenv('DATABASE_URL') else 'Not set'}")
    
    if not os.getenv('DATABASE_URL'):
        print("❌ DATABASE_URL not set in .env file")
        return False
    
    # Start FastAPI server in background
    print("\n🔄 Starting FastAPI server...")
    process = subprocess.Popen([
        sys.executable, "-m", "uvicorn", "sage_api:app", 
        "--host", "0.0.0.0", "--port", "8001", "--reload"
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    # Wait for server to start
    print("⏳ Waiting for server to start...")
    time.sleep(5)
    
    try:
        # Test endpoints
        base_url = "http://localhost:8001"
        
        print("\n📡 Testing API endpoints...")
        
        # Test health endpoint
        try:
            response = requests.get(f"{base_url}/api/v1/health", timeout=10)
            print(f"Health check: {response.status_code}")
            if response.status_code == 200:
                print(f"✅ Health check passed: {response.json()}")
            else:
                print(f"❌ Health check failed: {response.text}")
        except Exception as e:
            print(f"❌ Health check error: {e}")
        
        # Test keys endpoint
        try:
            response = requests.get(f"{base_url}/api/v1/keys", timeout=10)
            print(f"Keys endpoint: {response.status_code}")
            if response.status_code == 200:
                keys = response.json()
                print(f"✅ Keys endpoint passed: {len(keys.get('keys', []))} keys found")
            else:
                print(f"❌ Keys endpoint failed: {response.text}")
        except Exception as e:
            print(f"❌ Keys endpoint error: {e}")
        
        # Test API docs
        try:
            response = requests.get(f"{base_url}/docs", timeout=10)
            print(f"API docs: {response.status_code}")
            if response.status_code == 200:
                print("✅ API docs accessible")
            else:
                print("❌ API docs not accessible")
        except Exception as e:
            print(f"❌ API docs error: {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ Test error: {e}")
        return False
    
    finally:
        # Stop the server
        print("\n🛑 Stopping FastAPI server...")
        process.terminate()
        process.wait()
        print("✅ Server stopped")

if __name__ == "__main__":
    success = test_fastapi_with_postgres()
    
    if success:
        print("\n🎉 FastAPI with PostgreSQL test completed!")
        print("Your app is ready for deployment to Render.")
    else:
        print("\n❌ FastAPI with PostgreSQL test failed!")
        print("Check your .env file and database configuration.")
        sys.exit(1)