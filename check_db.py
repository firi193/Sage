#!/usr/bin/env python3
"""
Quick script to check what's in the Sage databases
"""

import sqlite3
import os

def check_database(db_path):
    if not os.path.exists(db_path):
        print(f"❌ Database {db_path} does not exist")
        return
    
    print(f"\n📊 Checking {db_path}:")
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        
        if not tables:
            print("  No tables found")
            return
            
        for (table_name,) in tables:
            print(f"\n  📋 Table: {table_name}")
            
            # Get table schema
            cursor.execute(f"PRAGMA table_info({table_name});")
            columns = cursor.fetchall()
            print("    Columns:", [col[1] for col in columns])
            
            # Get row count
            cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
            count = cursor.fetchone()[0]
            print(f"    Rows: {count}")
            
            # Show recent entries (limit 3)
            if count > 0:
                cursor.execute(f"SELECT * FROM {table_name} ORDER BY rowid DESC LIMIT 3;")
                rows = cursor.fetchall()
                print("    Recent entries:")
                for row in rows:
                    print(f"      {row}")
        
        conn.close()
        
    except Exception as e:
        print(f"  ❌ Error: {e}")

if __name__ == "__main__":
    databases = [
        "sage_keys.db",
        "sage_grants.db", 
        "sage_audit_logs.db",
        "sage_policy.db"
    ]
    
    for db in databases:
        check_database(db)
    
    print("\n✅ Database check complete!")