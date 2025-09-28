"""
Key storage service using configurable database for encrypted API key persistence
Supports both SQLite (development) and PostgreSQL (production)
"""

import sqlite3
import os
from datetime import datetime
from typing import List, Optional, Dict, Any
from contextlib import contextmanager

from ..models.stored_key import StoredKey
from ..config.database import get_db_connection, is_postgres
from ..utils.encryption import EncryptionManager


class KeyStorageService:
    """
    Configurable storage service for encrypted API keys
    Supports both SQLite (development) and PostgreSQL (production)
    """
    
    def __init__(self, encryption_manager: EncryptionManager = None):
        """
        Initialize key storage service
        
        Args:
            encryption_manager: Encryption manager for key protection
        """
        self.encryption_manager = encryption_manager or EncryptionManager()
        self._init_database()
    
    def _init_database(self) -> None:
        """Initialize database with required tables"""
        with get_db_connection('keys') as conn:
            if is_postgres():
                # PostgreSQL table creation
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS sage_keys_stored_keys (
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
                
                # Create indexes for better query performance
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_owner_id 
                    ON sage_keys_stored_keys(owner_id)
                """)
                
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_active_keys 
                    ON sage_keys_stored_keys(is_active, owner_id)
                """)
            else:
                # SQLite table creation
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS stored_keys (
                        key_id TEXT PRIMARY KEY,
                        owner_id TEXT NOT NULL,
                        key_name TEXT NOT NULL,
                        encrypted_key BLOB NOT NULL,
                        created_at TEXT NOT NULL,
                        last_rotated TEXT NOT NULL,
                        is_active INTEGER NOT NULL DEFAULT 1,
                        coral_session_id TEXT NOT NULL,
                        UNIQUE(owner_id, key_name)
                    )
                """)
                
                # Create indexes for better query performance
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_owner_id 
                    ON stored_keys(owner_id)
                """)
                
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_active_keys 
                    ON stored_keys(is_active, owner_id)
                """)
            
            conn.commit()
    
    def _get_table_name(self) -> str:
        """Get the correct table name based on database type"""
        return "sage_keys_stored_keys" if is_postgres() else "stored_keys"
    
    def _get_param_placeholder(self) -> str:
        """Get the correct parameter placeholder based on database type"""
        return "%s" if is_postgres() else "?"
    
    @contextmanager
    def _get_connection(self):
        """Context manager for database connections"""
        with get_db_connection('keys') as conn:
            if is_postgres():
                # PostgreSQL connection
                conn.row_factory = None  # PostgreSQL doesn't use row_factory
                yield conn
            else:
                # SQLite connection
                conn.row_factory = sqlite3.Row  # Enable column access by name
                yield conn
    
    def store_key(self, stored_key: StoredKey) -> bool:
        """
        Store an encrypted key in the database
        
        Args:
            stored_key: StoredKey instance to store
            
        Returns:
            True if successful, False otherwise
        """
        if not stored_key.validate():
            raise ValueError("Invalid StoredKey instance")
        
        try:
            with self._get_connection() as conn:
                table_name = self._get_table_name()
                placeholder = self._get_param_placeholder()
                
                conn.execute(f"""
                    INSERT INTO {table_name} 
                    (key_id, owner_id, key_name, encrypted_key, created_at, 
                     last_rotated, is_active, coral_session_id)
                    VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, 
                           {placeholder}, {placeholder}, {placeholder})
                """, (
                    stored_key.key_id,
                    stored_key.owner_id,
                    stored_key.key_name,
                    stored_key.encrypted_key,
                    stored_key.created_at.isoformat(),
                    stored_key.last_rotated.isoformat(),
                    1 if stored_key.is_active else 0,
                    stored_key.coral_session_id
                ))
                conn.commit()
                return True
        except (sqlite3.IntegrityError, Exception) as e:
            # Key already exists or constraint violation
            if is_postgres():
                import psycopg2
                if isinstance(e, psycopg2.IntegrityError):
                    return False
            return False
    
    def get_key(self, key_id: str) -> Optional[StoredKey]:
        """
        Retrieve a stored key by ID
        
        Args:
            key_id: Unique key identifier
            
        Returns:
            StoredKey instance if found, None otherwise
        """
        try:
            with self._get_connection() as conn:
                table_name = self._get_table_name()
                placeholder = self._get_param_placeholder()
                
                cursor = conn.execute(f"""
                    SELECT * FROM {table_name} WHERE key_id = {placeholder}
                """, (key_id,))
                row = cursor.fetchone()
                
                if row:
                    return self._row_to_stored_key(row)
                return None
        except Exception:
            return None
    
    def get_keys_by_owner(self, owner_id: str, active_only: bool = True) -> List[StoredKey]:
        """
        Retrieve all keys for a specific owner
        
        Args:
            owner_id: Owner's Coral ID
            active_only: If True, only return active keys
            
        Returns:
            List of StoredKey instances
        """
        try:
            with self._get_connection() as conn:
                table_name = self._get_table_name()
                placeholder = self._get_param_placeholder()
                
                if active_only:
                    cursor = conn.execute(f"""
                        SELECT * FROM {table_name} 
                        WHERE owner_id = {placeholder} AND is_active = 1
                        ORDER BY created_at DESC
                    """, (owner_id,))
                else:
                    cursor = conn.execute(f"""
                        SELECT * FROM {table_name} 
                        WHERE owner_id = {placeholder}
                        ORDER BY created_at DESC
                    """, (owner_id,))
                
                rows = cursor.fetchall()
                return [self._row_to_stored_key(row) for row in rows]
        except Exception:
            return []
    
    def update_key(self, stored_key: StoredKey) -> bool:
        """
        Update an existing stored key
        
        Args:
            stored_key: Updated StoredKey instance
            
        Returns:
            True if successful, False otherwise
        """
        if not stored_key.validate():
            raise ValueError("Invalid StoredKey instance")
        
        try:
            with self._get_connection() as conn:
                table_name = self._get_table_name()
                placeholder = self._get_param_placeholder()
                
                cursor = conn.execute(f"""
                    UPDATE {table_name} 
                    SET owner_id = {placeholder}, key_name = {placeholder}, encrypted_key = {placeholder}, 
                        last_rotated = {placeholder}, is_active = {placeholder}, coral_session_id = {placeholder}
                    WHERE key_id = {placeholder}
                """, (
                    stored_key.owner_id,
                    stored_key.key_name,
                    stored_key.encrypted_key,
                    stored_key.last_rotated.isoformat(),
                    1 if stored_key.is_active else 0,
                    stored_key.coral_session_id,
                    stored_key.key_id
                ))
                conn.commit()
                return cursor.rowcount > 0
        except Exception:
            return False
    
    def delete_key(self, key_id: str) -> bool:
        """
        Delete a stored key (hard delete)
        
        Args:
            key_id: Unique key identifier
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with self._get_connection() as conn:
                table_name = self._get_table_name()
                placeholder = self._get_param_placeholder()
                
                cursor = conn.execute(f"""
                    DELETE FROM {table_name} WHERE key_id = {placeholder}
                """, (key_id,))
                conn.commit()
                return cursor.rowcount > 0
        except Exception:
            return False
    
    def deactivate_key(self, key_id: str) -> bool:
        """
        Deactivate a stored key (soft delete)
        
        Args:
            key_id: Unique key identifier
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with self._get_connection() as conn:
                table_name = self._get_table_name()
                placeholder = self._get_param_placeholder()
                
                cursor = conn.execute(f"""
                    UPDATE {table_name} SET is_active = 0 WHERE key_id = {placeholder}
                """, (key_id,))
                conn.commit()
                return cursor.rowcount > 0
        except Exception:
            return False
    
    def verify_key_ownership(self, key_id: str, owner_id: str) -> bool:
        """
        Verify that a key belongs to the specified owner
        
        Args:
            key_id: Unique key identifier
            owner_id: Owner's Coral ID
            
        Returns:
            True if owner matches, False otherwise
        """
        try:
            with self._get_connection() as conn:
                table_name = self._get_table_name()
                placeholder = self._get_param_placeholder()
                
                cursor = conn.execute(f"""
                    SELECT 1 FROM {table_name} 
                    WHERE key_id = {placeholder} AND owner_id = {placeholder}
                """, (key_id, owner_id))
                return cursor.fetchone() is not None
        except Exception:
            return False
    
    def _row_to_stored_key(self, row) -> StoredKey:
        """
        Convert database row to StoredKey instance
        
        Args:
            row: Database row object (SQLite Row or PostgreSQL tuple)
            
        Returns:
            StoredKey instance
        """
        if is_postgres():
            # PostgreSQL returns tuples
            return StoredKey(
                key_id=row[0],
                owner_id=row[1],
                key_name=row[2],
                encrypted_key=row[3],
                created_at=datetime.fromisoformat(row[4]),
                last_rotated=datetime.fromisoformat(row[5]),
                is_active=bool(row[6]),
                coral_session_id=row[7]
            )
        else:
            # SQLite returns Row objects
            return StoredKey(
                key_id=row['key_id'],
                owner_id=row['owner_id'],
                key_name=row['key_name'],
                encrypted_key=row['encrypted_key'],
                created_at=datetime.fromisoformat(row['created_at']),
                last_rotated=datetime.fromisoformat(row['last_rotated']),
                is_active=bool(row['is_active']),
                coral_session_id=row['coral_session_id']
            )
    
    def get_storage_stats(self) -> Dict[str, Any]:
        """
        Get storage statistics
        
        Returns:
            Dictionary with storage statistics
        """
        try:
            with self._get_connection() as conn:
                table_name = self._get_table_name()
                
                cursor = conn.execute(f"""
                    SELECT 
                        COUNT(*) as total_keys,
                        COUNT(CASE WHEN is_active = 1 THEN 1 END) as active_keys,
                        COUNT(DISTINCT owner_id) as unique_owners
                    FROM {table_name}
                """)
                row = cursor.fetchone()
                
                if is_postgres():
                    return {
                        'total_keys': row[0],
                        'active_keys': row[1],
                        'unique_owners': row[2],
                        'database_type': 'PostgreSQL',
                        'table_name': table_name
                    }
                else:
                    return {
                        'total_keys': row['total_keys'],
                        'active_keys': row['active_keys'],
                        'unique_owners': row['unique_owners'],
                        'database_type': 'SQLite',
                        'table_name': table_name
                    }
        except Exception:
            return {
                'total_keys': 0,
                'active_keys': 0,
                'unique_owners': 0,
                'database_type': 'Unknown',
                'table_name': 'unknown'
            }