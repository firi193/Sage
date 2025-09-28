#!/usr/bin/env python3
"""
Quick test to verify PostgreSQL connection and data
"""

import os
from dotenv import load_dotenv
import psycopg2

load_dotenv()

def test_postgres_data():
    """Test PostgreSQL connection and data"""
    print("🔍 Testing PostgreSQL Connection and Data")
    print("=" * 50)
    
    try:
        # Connect to PostgreSQL
        conn = psycopg2.connect(os.getenv('DATABASE_URL'))
        cursor = conn.cursor()
        
        print("✅ Connected to PostgreSQL")
        
        # Test each table
        tables = [
            ('sage_keys_stored_keys', 'keys'),
            ('sage_grants_access_grants', 'grants'),
            ('sage_policy_usage_counters', 'usage counters'),
            ('sage_audit_audit_logs', 'audit logs')
        ]
        
        for table_name, description in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cursor.fetchone()[0]
            print(f"📊 {description}: {count} records")
            
            # Show sample data
            cursor.execute(f"SELECT * FROM {table_name} LIMIT 2")
            samples = cursor.fetchall()
            if samples:
                print(f"   Sample: {samples[0][:3]}...")  # Show first 3 columns
        
        cursor.close()
        conn.close()
        
        print("\n✅ PostgreSQL test completed successfully!")
        print("Your data is ready for the FastAPI app.")
        
        return True
        
    except Exception as e:
        print(f"❌ PostgreSQL test failed: {e}")
        return False

if __name__ == "__main__":
    test_postgres_data()