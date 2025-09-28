#!/usr/bin/env python3
"""
Check PostgreSQL schema for Sage tables
"""

import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

def check_postgres_schema():
    """Check the schema of PostgreSQL tables"""
    
    # Connect to PostgreSQL
    conn = psycopg2.connect(os.getenv('DATABASE_URL'))
    cursor = conn.cursor()
    
    try:
        # Check all tables
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name LIKE 'sage_%'
            ORDER BY table_name
        """)
        tables = cursor.fetchall()
        
        print('📋 PostgreSQL Tables:')
        for table in tables:
            print(f'  - {table[0]}')
        
        print()
        
        # Check schema for each table
        for table in tables:
            table_name = table[0]
            print(f'📋 Table: {table_name}')
            
            cursor.execute("""
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns 
                WHERE table_name = %s 
                ORDER BY ordinal_position
            """, (table_name,))
            columns = cursor.fetchall()
            
            for col in columns:
                nullable = "NULL" if col[2] == "YES" else "NOT NULL"
                default = f" DEFAULT {col[3]}" if col[3] else ""
                print(f'  - {col[0]}: {col[1]} ({nullable}){default}')
            
            # Check row count
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cursor.fetchone()[0]
            print(f'  Rows: {count}')
            print()
        
        # Check indexes
        print('🔍 Indexes:')
        cursor.execute("""
            SELECT 
                schemaname,
                tablename,
                indexname,
                indexdef
            FROM pg_indexes 
            WHERE schemaname = 'public' 
            AND tablename LIKE 'sage_%'
            ORDER BY tablename, indexname
        """)
        indexes = cursor.fetchall()
        
        for idx in indexes:
            print(f'  - {idx[2]} on {idx[1]}: {idx[3]}')
        
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    check_postgres_schema()