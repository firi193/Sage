"""
Key storage service using SQLite database for encrypted API key persistence
"""

import sqlite3
import os
from datetime import datetime
from typing import List, Optional, Dict, Any
from contextlib import contextmanager

from ..models.stored_key import StoredKey
from ..utils.encryption import EncryptionManager


class KeyStorageService:
    """
    SQLite-based storage service for encrypted API keys
    """
    
    def __init__(self, db_path: str = "sage_keys.db", encryption_manager: EncryptionManager = None):
        """
        Initialize key storage service
        
        Args:
            db_path: Path to SQLite database file
            encryption_manager: Encryption manager for key protection
        """
        self.db_path = db_path
        self.encryption_manager = encryption_manager or EncryptionManager()
        self._init_database()
    
    def _init_database(self) -> None:
        """Initialize SQLite database with required tables"""
        with self._get_connection() as conn:
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
    
    @contextmanager
    def _get_connection(self):
        """Context manager for database connections"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Enable column access by name
        try:
            yield conn
        finally:
            conn.close()
    
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
                conn.execute("""
                    INSERT INTO stored_keys 
                    (key_id, owner_id, key_name, encrypted_key, created_at, 
                     last_rotated, is_active, coral_session_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
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
        except sqlite3.IntegrityError:
            # Key already exists or constraint violation
            return False
        except Exception:
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
                cursor = conn.execute("""
                    SELECT * FROM stored_keys WHERE key_id = ?
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
                if active_only:
                    cursor = conn.execute("""
                        SELECT * FROM stored_keys 
                        WHERE owner_id = ? AND is_active = 1
                        ORDER BY created_at DESC
                    """, (owner_id,))
                else:
                    cursor = conn.execute("""
                        SELECT * FROM stored_keys 
                        WHERE owner_id = ?
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
                cursor = conn.execute("""
                    UPDATE stored_keys 
                    SET owner_id = ?, key_name = ?, encrypted_key = ?, 
                        last_rotated = ?, is_active = ?, coral_session_id = ?
                    WHERE key_id = ?
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
                cursor = conn.execute("""
                    DELETE FROM stored_keys WHERE key_id = ?
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
                cursor = conn.execute("""
                    UPDATE stored_keys SET is_active = 0 WHERE key_id = ?
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
                cursor = conn.execute("""
                    SELECT 1 FROM stored_keys 
                    WHERE key_id = ? AND owner_id = ?
                """, (key_id, owner_id))
                return cursor.fetchone() is not None
        except Exception:
            return False
    
    def _row_to_stored_key(self, row: sqlite3.Row) -> StoredKey:
        """
        Convert SQLite row to StoredKey instance
        
        Args:
            row: SQLite row object
            
        Returns:
            StoredKey instance
        """
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
                cursor = conn.execute("""
                    SELECT 
                        COUNT(*) as total_keys,
                        COUNT(CASE WHEN is_active = 1 THEN 1 END) as active_keys,
                        COUNT(DISTINCT owner_id) as unique_owners
                    FROM stored_keys
                """)
                row = cursor.fetchone()
                
                return {
                    'total_keys': row['total_keys'],
                    'active_keys': row['active_keys'],
                    'unique_owners': row['unique_owners'],
                    'database_path': self.db_path,
                    'database_exists': os.path.exists(self.db_path)
                }
        except Exception:
            return {
                'total_keys': 0,
                'active_keys': 0,
                'unique_owners': 0,
                'database_path': self.db_path,
                'database_exists': False
            }