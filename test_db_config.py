#!/usr/bin/env python3
"""
Test script to verify database configuration
"""

import os
from sage.config.database import db_config, is_postgres, get_table_prefix

def test_database_config():
    """Test database configuration"""
    print("🔍 Testing Database Configuration")
    print("=" * 40)
    
    # Check environment variables
    print(f"ENVIRONMENT: {os.getenv('ENVIRONMENT', 'Not set')}")
    print(f"DATABASE_URL: {'Set' if os.getenv('DATABASE_URL') else 'Not set'}")
    
    # Check configuration
    print(f"Using PostgreSQL: {is_postgres()}")
    
    # Get connection parameters
    params = db_config.get_connection_params()
    print(f"Database Type: {params['type']}")
    
    if params['type'] == 'postgres':
        print(f"PostgreSQL Host: {params['host']}")
        print(f"PostgreSQL Database: {params['database']}")
        print(f"PostgreSQL User: {params['user']}")
    else:
        print("SQLite Databases:")
        for key, value in params.items():
            if key != 'type':
                print(f"  {key}: {value}")
    
    # Test connection
    try:
        print("\n🔌 Testing Database Connection...")
        with db_config.get_connection('keys') as conn:
            print("✅ Database connection successful!")
            
            if is_postgres():
                # Test PostgreSQL connection
                cursor = conn.cursor()
                cursor.execute("SELECT version()")
                version = cursor.fetchone()[0]
                print(f"PostgreSQL Version: {version}")
            else:
                # Test SQLite connection
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = cursor.fetchall()
                print(f"SQLite Tables: {[table[0] for table in tables]}")
                
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False
    
    print("\n✅ Database configuration test completed successfully!")
    return True

if __name__ == "__main__":
    test_database_config()