#!/usr/bin/env python3
"""
Migration script to move SQLite data to PostgreSQL
Run this when you're ready to deploy to production
"""

import os
import sqlite3
import psycopg2
from psycopg2.extras import RealDictCursor
import json
from datetime import datetime
from sage.config.database import db_config

def migrate_sqlite_to_postgres():
    """Migrate all SQLite databases to PostgreSQL"""
    
    if not db_config.use_postgres:
        print("❌ Not configured for PostgreSQL. Set ENVIRONMENT=production and DATABASE_URL")
        return
    
    print("🚀 Starting migration from SQLite to PostgreSQL...")
    
    # Get PostgreSQL connection
    with db_config.get_connection() as pg_conn:
        cursor = pg_conn.cursor()
        
        # Create tables in PostgreSQL
        create_postgres_tables(cursor)
        pg_conn.commit()
        
        # Migrate each database
        migrate_keys_db(cursor)
        migrate_grants_db(cursor) 
        migrate_policy_db(cursor)
        migrate_audit_db(cursor)
        
        pg_conn.commit()
        print("✅ Migration completed successfully!")

def create_postgres_tables(cursor):
    """Create PostgreSQL tables with proper schema"""
    
    # Drop existing tables if they exist (for clean migration)
    print("🗑️  Dropping existing tables...")
    cursor.execute("DROP TABLE IF EXISTS sage_audit_audit_logs CASCADE")
    cursor.execute("DROP TABLE IF EXISTS sage_policy_usage_counters CASCADE")
    cursor.execute("DROP TABLE IF EXISTS sage_grants_access_grants CASCADE")
    cursor.execute("DROP TABLE IF EXISTS sage_keys_stored_keys CASCADE")
    
    # Keys table
    cursor.execute("""
        CREATE TABLE sage_keys_stored_keys (
            key_id TEXT PRIMARY KEY,
            owner_id TEXT NOT NULL,
            key_name TEXT NOT NULL,
            encrypted_key BYTEA NOT NULL,
            created_at TEXT NOT NULL,
            last_rotated TEXT NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1,
            coral_session_id TEXT NOT NULL,
            UNIQUE(owner_id, key_name)
        )
    """)
    
    # Grants table  
    cursor.execute("""
        CREATE TABLE sage_grants_access_grants (
            grant_id TEXT PRIMARY KEY,
            key_id TEXT NOT NULL,
            caller_id TEXT NOT NULL,
            permissions TEXT NOT NULL,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1,
            granted_by TEXT NOT NULL,
            UNIQUE(key_id, caller_id)
        )
    """)
    
    # Policy table
    cursor.execute("""
        CREATE TABLE sage_policy_usage_counters (
            key_id TEXT NOT NULL,
            caller_id TEXT NOT NULL,
            date TEXT NOT NULL,
            call_count INTEGER NOT NULL DEFAULT 0,
            total_payload_size INTEGER NOT NULL DEFAULT 0,
            average_response_time REAL NOT NULL DEFAULT 0.0,
            last_reset TEXT NOT NULL,
            PRIMARY KEY (key_id, caller_id, date)
        )
    """)
    
    # Audit logs table
    cursor.execute("""
        CREATE TABLE sage_audit_audit_logs (
            log_id TEXT PRIMARY KEY,
            timestamp TEXT NOT NULL,
            caller_id TEXT NOT NULL,
            key_id TEXT NOT NULL,
            action TEXT NOT NULL,
            method TEXT NOT NULL,
            endpoint TEXT NOT NULL,
            payload_size INTEGER NOT NULL DEFAULT 0,
            response_time REAL NOT NULL DEFAULT 0.0,
            response_code INTEGER NOT NULL,
            error_message TEXT,
            created_at TEXT NOT NULL
        )
    """)

def migrate_keys_db(cursor):
    """Migrate keys database"""
    print("📦 Migrating keys database...")
    
    if not os.path.exists('sage_keys.db'):
        print("  ⚠️  sage_keys.db not found, skipping...")
        return
        
    with sqlite3.connect('sage_keys.db') as sqlite_conn:
        sqlite_conn.row_factory = sqlite3.Row
        sqlite_cursor = sqlite_conn.cursor()
        
        sqlite_cursor.execute("SELECT * FROM stored_keys")
        rows = sqlite_cursor.fetchall()
        
        for row in rows:
            cursor.execute("""
                INSERT INTO sage_keys_stored_keys 
                (key_id, owner_id, key_name, encrypted_key, created_at, last_rotated, is_active, coral_session_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (key_id) DO NOTHING
            """, (
                row['key_id'], row['owner_id'], row['key_name'], 
                row['encrypted_key'], row['created_at'], row['last_rotated'],
                row['is_active'], row['coral_session_id']
            ))
        
        print(f"  ✅ Migrated {len(rows)} keys")

def migrate_grants_db(cursor):
    """Migrate grants database"""
    print("🔐 Migrating grants database...")
    
    if not os.path.exists('sage_grants.db'):
        print("  ⚠️  sage_grants.db not found, skipping...")
        return
        
    with sqlite3.connect('sage_grants.db') as sqlite_conn:
        sqlite_conn.row_factory = sqlite3.Row
        sqlite_cursor = sqlite_conn.cursor()
        
        sqlite_cursor.execute("SELECT * FROM access_grants")
        rows = sqlite_cursor.fetchall()
        
        for row in rows:
            cursor.execute("""
                INSERT INTO sage_grants_access_grants 
                (grant_id, key_id, caller_id, permissions, created_at, expires_at, is_active, granted_by)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (grant_id) DO NOTHING
            """, (
                row['grant_id'], row['key_id'], row['caller_id'],
                row['permissions'], row['created_at'], row['expires_at'],
                row['is_active'], row['granted_by']
            ))
        
        print(f"  ✅ Migrated {len(rows)} grants")

def migrate_policy_db(cursor):
    """Migrate policy database"""
    print("📊 Migrating policy database...")
    
    if not os.path.exists('sage_policy.db'):
        print("  ⚠️  sage_policy.db not found, skipping...")
        return
        
    with sqlite3.connect('sage_policy.db') as sqlite_conn:
        sqlite_conn.row_factory = sqlite3.Row
        sqlite_cursor = sqlite_conn.cursor()
        
        sqlite_cursor.execute("SELECT * FROM usage_counters")
        rows = sqlite_cursor.fetchall()
        
        for row in rows:
            cursor.execute("""
                INSERT INTO sage_policy_usage_counters 
                (key_id, caller_id, date, call_count, total_payload_size, average_response_time, last_reset)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (key_id, caller_id, date) DO NOTHING
            """, (
                row['key_id'], row['caller_id'], row['date'],
                row['call_count'], row['total_payload_size'], 
                row['average_response_time'], row['last_reset']
            ))
        
        print(f"  ✅ Migrated {len(rows)} usage counters")

def migrate_audit_db(cursor):
    """Migrate audit logs database"""
    print("📝 Migrating audit logs database...")
    
    if not os.path.exists('sage_audit_logs.db'):
        print("  ⚠️  sage_audit_logs.db not found, skipping...")
        return
        
    with sqlite3.connect('sage_audit_logs.db') as sqlite_conn:
        sqlite_conn.row_factory = sqlite3.Row
        sqlite_cursor = sqlite_conn.cursor()
        
        sqlite_cursor.execute("SELECT * FROM audit_logs")
        rows = sqlite_cursor.fetchall()
        
        for row in rows:
            cursor.execute("""
                INSERT INTO sage_audit_audit_logs 
                (log_id, timestamp, caller_id, key_id, action, method, endpoint,
                 payload_size, response_time, response_code, error_message, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (log_id) DO NOTHING
            """, (
                row['log_id'], row['timestamp'], row['caller_id'], row['key_id'],
                row['action'], row['method'], row['endpoint'], row['payload_size'],
                row['response_time'], row['response_code'], row['error_message'],
                row['created_at']
            ))
        
        print(f"  ✅ Migrated {len(rows)} audit logs")

if __name__ == "__main__":
    migrate_sqlite_to_postgres()