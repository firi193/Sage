"""
Authorization Engine for Sage - handles access grants and caller permissions
"""

import sqlite3
import os
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from contextlib import contextmanager
import logging

from ..models.access_grant import AccessGrant


logger = logging.getLogger(__name__)


class AuthorizationEngine:
    """
    Authorization engine that manages access grants and validates caller permissions
    Handles grant creation, validation, expiration, and cleanup processes
    """
    
    def __init__(self, db_path: str = "sage_grants.db"):
        """
        Initialize authorization engine with SQLite storage
        
        Args:
            db_path: Path to SQLite database file for grants
        """
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self) -> None:
        """Initialize SQLite database with required tables"""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS access_grants (
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
            
            # Create indexes for better query performance
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_key_caller 
                ON access_grants(key_id, caller_id)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_active_grants 
                ON access_grants(is_active, expires_at)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_granted_by 
                ON access_grants(granted_by)
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
    
    def _row_to_access_grant(self, row) -> AccessGrant:
        """Convert database row to AccessGrant instance"""
        import json
        
        return AccessGrant(
            grant_id=row['grant_id'],
            key_id=row['key_id'],
            caller_id=row['caller_id'],
            permissions=json.loads(row['permissions']),
            created_at=datetime.fromisoformat(row['created_at']),
            expires_at=datetime.fromisoformat(row['expires_at']),
            is_active=bool(row['is_active']),
            granted_by=row['granted_by']
        )
    
    async def create_grant(self, key_id: str, caller_id: str, permissions: Dict[str, Any], 
                          expires_at: datetime, owner_id: str, _allow_past_expiry: bool = False) -> str:
        """
        Create a new access grant for a caller to use a specific key
        
        Args:
            key_id: ID of the key to grant access to
            caller_id: Coral wallet/session ID of the caller
            permissions: Dictionary containing permission settings
            expires_at: When the grant expires
            owner_id: Coral ID of the key owner granting access
            
        Returns:
            grant_id: Unique identifier for the created grant
            
        Raises:
            ValueError: If parameters are invalid
            RuntimeError: If grant creation fails
        """
        # Validate inputs
        if not key_id or not key_id.strip():
            raise ValueError("Key ID cannot be empty")
        
        if not caller_id or not caller_id.strip():
            raise ValueError("Caller ID cannot be empty")
        
        if not owner_id or not owner_id.strip():
            raise ValueError("Owner ID cannot be empty")
        
        if not isinstance(permissions, dict):
            raise ValueError("Permissions must be a dictionary")
        
        if not _allow_past_expiry and expires_at <= datetime.utcnow():
            raise ValueError("Expiry time must be in the future")
        
        # Validate required permissions
        if 'max_calls_per_day' not in permissions:
            raise ValueError("Permissions must include max_calls_per_day")
        
        if not isinstance(permissions['max_calls_per_day'], int) or permissions['max_calls_per_day'] <= 0:
            raise ValueError("max_calls_per_day must be a positive integer")
        
        try:
            # Create new grant
            grant = AccessGrant.create_new(
                key_id=key_id,
                caller_id=caller_id,
                permissions=permissions,
                expires_at=expires_at,
                granted_by=owner_id
            )
            
            # Store in database
            import json
            with self._get_connection() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO access_grants 
                    (grant_id, key_id, caller_id, permissions, created_at, 
                     expires_at, is_active, granted_by)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    grant.grant_id,
                    grant.key_id,
                    grant.caller_id,
                    json.dumps(grant.permissions),
                    grant.created_at.isoformat(),
                    grant.expires_at.isoformat(),
                    1 if grant.is_active else 0,
                    grant.granted_by
                ))
                conn.commit()
            
            logger.info(f"Created grant {grant.grant_id} for caller {caller_id} on key {key_id}")
            return grant.grant_id
            
        except Exception as e:
            logger.error(f"Failed to create grant for caller {caller_id} on key {key_id}: {str(e)}")
            raise RuntimeError(f"Grant creation failed: {str(e)}")
    
    async def check_authorization(self, key_id: str, caller_session: str) -> bool:
        """
        Check if a caller is authorized to use a specific key
        
        Args:
            key_id: ID of the key to check access for
            caller_session: Coral session ID of the caller
            
        Returns:
            True if authorized, False otherwise
        """
        if not key_id or not caller_session:
            return False
        
        try:
            with self._get_connection() as conn:
                cursor = conn.execute("""
                    SELECT * FROM access_grants 
                    WHERE key_id = ? AND caller_id = ? AND is_active = 1
                """, (key_id, caller_session))
                row = cursor.fetchone()
                
                if not row:
                    logger.debug(f"No active grant found for caller {caller_session} on key {key_id}")
                    return False
                
                grant = self._row_to_access_grant(row)
                
                # Check if grant is valid (not expired)
                if grant.is_expired():
                    logger.debug(f"Grant {grant.grant_id} has expired")
                    # Automatically deactivate expired grant
                    await self._deactivate_grant(grant.grant_id)
                    return False
                
                logger.debug(f"Authorization granted for caller {caller_session} on key {key_id}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to check authorization for caller {caller_session} on key {key_id}: {str(e)}")
            return False
    
    async def get_grant(self, key_id: str, caller_id: str) -> Optional[AccessGrant]:
        """
        Get the active grant for a specific key and caller
        
        Args:
            key_id: ID of the key
            caller_id: Coral ID of the caller
            
        Returns:
            AccessGrant instance if found and active, None otherwise
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.execute("""
                    SELECT * FROM access_grants 
                    WHERE key_id = ? AND caller_id = ? AND is_active = 1
                """, (key_id, caller_id))
                row = cursor.fetchone()
                
                if row:
                    grant = self._row_to_access_grant(row)
                    # Check if expired
                    if grant.is_expired():
                        await self._deactivate_grant(grant.grant_id)
                        return None
                    return grant
                return None
                
        except Exception as e:
            logger.error(f"Failed to get grant for caller {caller_id} on key {key_id}: {str(e)}")
            return None
    
    async def revoke_grant(self, grant_id: str, owner_id: str) -> bool:
        """
        Revoke a specific access grant
        
        Args:
            grant_id: Unique grant identifier
            owner_id: Coral ID of the key owner
            
        Returns:
            True if revocation successful, False otherwise
            
        Raises:
            ValueError: If grant not found or owner mismatch
            RuntimeError: If revocation operation fails
        """
        if not grant_id or not owner_id:
            raise ValueError("Grant ID and owner ID cannot be empty")
        
        try:
            with self._get_connection() as conn:
                # First verify the grant exists and belongs to the owner
                cursor = conn.execute("""
                    SELECT granted_by FROM access_grants 
                    WHERE grant_id = ? AND is_active = 1
                """, (grant_id,))
                row = cursor.fetchone()
                
                if not row:
                    raise ValueError(f"Grant not found or already inactive: {grant_id}")
                
                if row['granted_by'] != owner_id:
                    raise ValueError("Access denied: grant not owned by requester")
                
                # Deactivate the grant
                conn.execute("""
                    UPDATE access_grants 
                    SET is_active = 0 
                    WHERE grant_id = ?
                """, (grant_id,))
                conn.commit()
                
                logger.info(f"Revoked grant {grant_id} by owner {owner_id}")
                return True
                
        except ValueError:
            # Re-raise validation errors
            raise
        except Exception as e:
            logger.error(f"Failed to revoke grant {grant_id} by owner {owner_id}: {str(e)}")
            raise RuntimeError(f"Grant revocation failed: {str(e)}")
    
    async def revoke_grants_for_key(self, key_id: str, owner_id: str) -> int:
        """
        Revoke all grants for a specific key (used when key is revoked)
        
        Args:
            key_id: ID of the key
            owner_id: Coral ID of the key owner
            
        Returns:
            Number of grants revoked
        """
        if not key_id or not owner_id:
            return 0
        
        try:
            with self._get_connection() as conn:
                cursor = conn.execute("""
                    UPDATE access_grants 
                    SET is_active = 0 
                    WHERE key_id = ? AND granted_by = ? AND is_active = 1
                """, (key_id, owner_id))
                conn.commit()
                
                revoked_count = cursor.rowcount
                logger.info(f"Revoked {revoked_count} grants for key {key_id}")
                return revoked_count
                
        except Exception as e:
            logger.error(f"Failed to revoke grants for key {key_id}: {str(e)}")
            return 0
    
    async def cleanup_expired_grants(self) -> int:
        """
        Clean up expired grants by deactivating them
        
        Returns:
            Number of grants cleaned up
        """
        try:
            current_time = datetime.utcnow().isoformat()
            
            with self._get_connection() as conn:
                cursor = conn.execute("""
                    UPDATE access_grants 
                    SET is_active = 0 
                    WHERE is_active = 1 AND expires_at < ?
                """, (current_time,))
                conn.commit()
                
                cleaned_count = cursor.rowcount
                if cleaned_count > 0:
                    logger.info(f"Cleaned up {cleaned_count} expired grants")
                return cleaned_count
                
        except Exception as e:
            logger.error(f"Failed to cleanup expired grants: {str(e)}")
            return 0
    
    async def _deactivate_grant(self, grant_id: str) -> bool:
        """
        Internal method to deactivate a grant
        
        Args:
            grant_id: Grant to deactivate
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with self._get_connection() as conn:
                conn.execute("""
                    UPDATE access_grants 
                    SET is_active = 0 
                    WHERE grant_id = ?
                """, (grant_id,))
                conn.commit()
                return True
        except Exception:
            return False
    
    async def list_grants_by_owner(self, owner_id: str, active_only: bool = True) -> List[Dict[str, Any]]:
        """
        List all grants created by a specific owner
        
        Args:
            owner_id: Coral ID of the grant owner
            active_only: If True, only return active grants
            
        Returns:
            List of grant metadata dictionaries
        """
        if not owner_id:
            return []
        
        try:
            with self._get_connection() as conn:
                if active_only:
                    cursor = conn.execute("""
                        SELECT * FROM access_grants 
                        WHERE granted_by = ? AND is_active = 1
                        ORDER BY created_at DESC
                    """, (owner_id,))
                else:
                    cursor = conn.execute("""
                        SELECT * FROM access_grants 
                        WHERE granted_by = ?
                        ORDER BY created_at DESC
                    """, (owner_id,))
                
                grants = []
                for row in cursor.fetchall():
                    grant = self._row_to_access_grant(row)
                    grants.append({
                        'grant_id': grant.grant_id,
                        'key_id': grant.key_id,
                        'caller_id': grant.caller_id,
                        'permissions': grant.permissions,
                        'created_at': grant.created_at.isoformat(),
                        'expires_at': grant.expires_at.isoformat(),
                        'is_active': grant.is_active,
                        'is_expired': grant.is_expired()
                    })
                
                return grants
                
        except Exception as e:
            logger.error(f"Failed to list grants for owner {owner_id}: {str(e)}")
            return []
    
    async def validate_coral_identity(self, session_id: str, wallet_id: str = None) -> str:
        """
        Validate Coral identity (session/wallet ID)
        For MVP, this is a simple validation - in production would integrate with Coral
        
        Args:
            session_id: Coral session ID
            wallet_id: Optional Coral wallet ID
            
        Returns:
            Validated caller ID
            
        Raises:
            ValueError: If identity validation fails
        """
        if not session_id or not session_id.strip():
            raise ValueError("Session ID cannot be empty")
        
        # For MVP, we'll use session_id as the caller_id
        # In production, this would validate against Coral's identity system
        if len(session_id) < 8:  # Basic validation
            raise ValueError("Invalid session ID format")
        
        return session_id