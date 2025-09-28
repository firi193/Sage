#!/usr/bin/env python3
"""
Test KeyStorageService with PostgreSQL
"""

import os
from dotenv import load_dotenv

load_dotenv()

def test_key_storage_postgres():
    """Test KeyStorageService with PostgreSQL"""
    print("🔍 Testing KeyStorageService with PostgreSQL")
    print("=" * 50)
    
    try:
        from sage.services.key_storage import KeyStorageService
        
        print("📦 Creating KeyStorageService...")
        storage = KeyStorageService()
        
        print("✅ KeyStorageService created successfully!")
        
        # Test database connection
        print("\n🔌 Testing database connection...")
        with storage._get_connection() as cursor:
            cursor.execute("SELECT COUNT(*) FROM sage_keys_stored_keys")
            count = cursor.fetchone()[0]
            print(f"✅ Connected to PostgreSQL: {count} keys found")
        
        # Test storage stats
        print("\n📊 Testing storage stats...")
        stats = storage.get_storage_stats()
        print(f"Storage stats: {stats}")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_key_storage_postgres()
    
    if success:
        print("\n🎉 KeyStorageService PostgreSQL test passed!")
    else:
        print("\n❌ KeyStorageService PostgreSQL test failed!")