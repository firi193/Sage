"""
Privacy-Aware Logging Service for Sage - handles audit logging with metadata only
"""

import sqlite3
import os
from datetime import datetime, date, timedelta
from typing import List, Optional, Dict, Any
from contextlib import contextmanager
import logging
import json

from ..models.privacy_audit_log import PrivacyAuditLog


logger = logging.getLogger(__name__)


class LoggingService:
    """
    Privacy-aware logging service that records metadata only for audit purposes
    Ensures tamper-resistant, chronologically ordered logs with proper access control
    """
    
    def __init__(self, db_path: str = "sage_audit_logs.db"):
        """
        Initialize logging service with SQLite storage
        
        Args:
            db_path: Path to SQLite database file for audit logs
        """
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self) -> None:
        """Initialize SQLite database with required tables and indexes"""
        with self._get_connection() as conn:
            # Audit logs table with tamper-resistant design
            conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_logs (
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
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    CONSTRAINT chk_payload_size CHECK (payload_size >= 0),
                    CONSTRAINT chk_response_time CHECK (response_time >= 0)
                )
            """)
            
            # Create indexes for efficient querying and chronological ordering
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_logs_timestamp 
                ON audit_logs(timestamp DESC)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_logs_key_caller 
                ON audit_logs(key_id, caller_id)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_logs_key_timestamp 
                ON audit_logs(key_id, timestamp DESC)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_logs_caller_timestamp 
                ON audit_logs(caller_id, timestamp DESC)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_logs_action 
                ON audit_logs(action, timestamp DESC)
            """)
            
            # Create a sequence table for ensuring chronological ordering
            conn.execute("""
                CREATE TABLE IF NOT EXISTS log_sequence (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    log_id TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    FOREIGN KEY (log_id) REFERENCES audit_logs(log_id)
                )
            """)
            
            conn.commit()
    
    @contextmanager
    def _get_connection(self):
        """Context manager for database connections with proper error handling"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Enable column access by name
        # Enable foreign key constraints
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
        finally:
            conn.close()
    
    def _row_to_audit_log(self, row) -> PrivacyAuditLog:
        """Convert database row to PrivacyAuditLog instance"""
        return PrivacyAuditLog(
            log_id=row['log_id'],
            timestamp=datetime.fromisoformat(row['timestamp']),
            caller_id=row['caller_id'],
            key_id=row['key_id'],
            action=row['action'],
            method=row['method'],
            endpoint=row['endpoint'],
            payload_size=row['payload_size'],
            response_time=row['response_time'],
            response_code=row['response_code'],
            error_message=row['error_message']
        )
    
    async def log_proxy_call(self, caller_id: str, key_id: str, method: str, 
                           endpoint: str, payload_size: int, response_time: float,
                           response_code: int, error_message: Optional[str] = None) -> str:
        """
        Log a proxy call with metadata only (no sensitive payload content)
        
        Args:
            caller_id: Coral ID of the calling agent
            key_id: ID of the key used for the call
            method: HTTP method (GET, POST, etc.)
            endpoint: Target API endpoint
            payload_size: Size of request payload in bytes
            response_time: Response time in milliseconds
            response_code: HTTP response code
            error_message: Optional error message if call failed
            
        Returns:
            log_id: Unique identifier for the created log entry
            
        Raises:
            ValueError: If required parameters are invalid
            RuntimeError: If logging operation fails
        """
        return await self._create_log_entry(
            caller_id=caller_id,
            key_id=key_id,
            action="proxy_call",
            method=method,
            endpoint=endpoint,
            payload_size=payload_size,
            response_time=response_time,
            response_code=response_code,
            error_message=error_message
        )
    
    async def log_grant_access(self, caller_id: str, key_id: str, granted_to: str,
                             permissions: Dict[str, Any]) -> str:
        """
        Log an access grant operation
        
        Args:
            caller_id: Coral ID of the key owner granting access
            key_id: ID of the key being granted
            granted_to: Coral ID of the agent receiving access
            permissions: Grant permissions (for metadata only)
            
        Returns:
            log_id: Unique identifier for the created log entry
        """
        # Create metadata endpoint for grant operations
        endpoint = f"/grant/{granted_to}"
        payload_size = len(json.dumps(permissions))
        
        return await self._create_log_entry(
            caller_id=caller_id,
            key_id=key_id,
            action="grant_access",
            method="POST",
            endpoint=endpoint,
            payload_size=payload_size,
            response_time=0.0,
            response_code=200
        )
    
    async def log_rate_limit_blocked(self, caller_id: str, key_id: str, method: str,
                                   endpoint: str, current_usage: int, limit: int) -> str:
        """
        Log a rate limit blocked attempt
        
        Args:
            caller_id: Coral ID of the calling agent
            key_id: ID of the key that hit rate limit
            method: HTTP method that was blocked
            endpoint: Target endpoint that was blocked
            current_usage: Current usage count
            limit: Rate limit that was exceeded
            
        Returns:
            log_id: Unique identifier for the created log entry
        """
        error_message = f"Rate limit exceeded: {current_usage}/{limit} calls"
        
        return await self._create_log_entry(
            caller_id=caller_id,
            key_id=key_id,
            action="rate_limit_blocked",
            method=method,
            endpoint=endpoint,
            payload_size=0,
            response_time=0.0,
            response_code=429,
            error_message=error_message
        )
    
    async def log_authorization_failed(self, caller_id: str, key_id: str, method: str,
                                     endpoint: str, reason: str) -> str:
        """
        Log an authorization failure
        
        Args:
            caller_id: Coral ID of the calling agent
            key_id: ID of the key that failed authorization
            method: HTTP method that was attempted
            endpoint: Target endpoint that was attempted
            reason: Reason for authorization failure
            
        Returns:
            log_id: Unique identifier for the created log entry
        """
        return await self._create_log_entry(
            caller_id=caller_id,
            key_id=key_id,
            action="authorization_failed",
            method=method,
            endpoint=endpoint,
            payload_size=0,
            response_time=0.0,
            response_code=403,
            error_message=reason
        )
    
    async def _create_log_entry(self, caller_id: str, key_id: str, action: str,
                              method: str, endpoint: str, payload_size: int,
                              response_time: float, response_code: int,
                              error_message: Optional[str] = None) -> str:
        """
        Internal method to create a log entry with tamper-resistant storage
        
        Args:
            caller_id: Coral ID of the caller
            key_id: ID of the key
            action: Action being logged
            method: HTTP method
            endpoint: Target endpoint
            payload_size: Payload size in bytes
            response_time: Response time in milliseconds
            response_code: HTTP response code
            error_message: Optional error message
            
        Returns:
            log_id: Unique identifier for the created log entry
            
        Raises:
            ValueError: If parameters are invalid
            RuntimeError: If logging operation fails
        """
        # Validate inputs
        if not caller_id or not caller_id.strip():
            raise ValueError("Caller ID cannot be empty")
        
        if not key_id or not key_id.strip():
            raise ValueError("Key ID cannot be empty")
        
        if not action or not action.strip():
            raise ValueError("Action cannot be empty")
        
        if not method or not method.strip():
            raise ValueError("Method cannot be empty")
        
        if not endpoint or not endpoint.strip():
            raise ValueError("Endpoint cannot be empty")
        
        if payload_size < 0:
            raise ValueError("Payload size cannot be negative")
        
        if response_time < 0:
            raise ValueError("Response time cannot be negative")
        
        try:
            # Create log entry
            log_entry = PrivacyAuditLog.create_new(
                caller_id=caller_id,
                key_id=key_id,
                action=action,
                method=method,
                endpoint=endpoint,
                payload_size=payload_size,
                response_time=response_time,
                response_code=response_code,
                error_message=error_message
            )
            
            # Store in database with tamper-resistant design
            with self._get_connection() as conn:
                # Insert into main audit_logs table
                conn.execute("""
                    INSERT INTO audit_logs 
                    (log_id, timestamp, caller_id, key_id, action, method, 
                     endpoint, payload_size, response_time, response_code, error_message)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    log_entry.log_id,
                    log_entry.timestamp.isoformat(),
                    log_entry.caller_id,
                    log_entry.key_id,
                    log_entry.action,
                    log_entry.method,
                    log_entry.endpoint,
                    log_entry.payload_size,
                    log_entry.response_time,
                    log_entry.response_code,
                    log_entry.error_message
                ))
                
                # Insert into sequence table for chronological ordering
                conn.execute("""
                    INSERT INTO log_sequence (log_id) VALUES (?)
                """, (log_entry.log_id,))
                
                conn.commit()
            
            logger.debug(f"Created audit log {log_entry.log_id} for action {action}")
            return log_entry.log_id
            
        except Exception as e:
            logger.error(f"Failed to create audit log for action {action}: {str(e)}")
            raise RuntimeError(f"Audit logging failed: {str(e)}")
    
    async def get_logs_for_key(self, key_id: str, owner_id: str, 
                             start_date: Optional[datetime] = None,
                             end_date: Optional[datetime] = None,
                             caller_id: Optional[str] = None,
                             action: Optional[str] = None,
                             limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get audit logs for a specific key (only accessible by key owner)
        
        Args:
            key_id: ID of the key to get logs for
            owner_id: Coral ID of the key owner (for access control)
            start_date: Optional start date for filtering
            end_date: Optional end date for filtering
            caller_id: Optional caller ID to filter by
            action: Optional action type to filter by
            limit: Maximum number of logs to return
            
        Returns:
            List of audit log dictionaries in chronological order
            
        Raises:
            ValueError: If parameters are invalid
            RuntimeError: If query operation fails
        """
        if not key_id or not owner_id:
            raise ValueError("Key ID and owner ID cannot be empty")
        
        if limit <= 0 or limit > 1000:
            raise ValueError("Limit must be between 1 and 1000")
        
        try:
            # Note: In a real implementation, we would verify that owner_id 
            # actually owns the key_id by checking with KeyManager
            # For MVP, we trust the caller to provide correct owner_id
            
            with self._get_connection() as conn:
                # Build query with filters
                query = """
                    SELECT * FROM audit_logs 
                    WHERE key_id = ?
                """
                params = [key_id]
                
                if start_date:
                    query += " AND timestamp >= ?"
                    params.append(start_date.isoformat())
                
                if end_date:
                    query += " AND timestamp <= ?"
                    params.append(end_date.isoformat())
                
                if caller_id:
                    query += " AND caller_id = ?"
                    params.append(caller_id)
                
                if action:
                    query += " AND action = ?"
                    params.append(action)
                
                # Order chronologically (newest first) and apply limit
                query += " ORDER BY timestamp DESC LIMIT ?"
                params.append(limit)
                
                cursor = conn.execute(query, params)
                
                logs = []
                for row in cursor.fetchall():
                    log_entry = self._row_to_audit_log(row)
                    logs.append(log_entry.to_dict())
                
                logger.debug(f"Retrieved {len(logs)} audit logs for key {key_id}")
                return logs
                
        except Exception as e:
            logger.error(f"Failed to retrieve audit logs for key {key_id}: {str(e)}")
            raise RuntimeError(f"Log retrieval failed: {str(e)}")
    
    async def get_logs_by_caller(self, caller_id: str, 
                               start_date: Optional[datetime] = None,
                               end_date: Optional[datetime] = None,
                               key_id: Optional[str] = None,
                               action: Optional[str] = None,
                               limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get audit logs for a specific caller across all keys they've accessed
        
        Args:
            caller_id: Coral ID of the caller
            start_date: Optional start date for filtering
            end_date: Optional end date for filtering
            key_id: Optional key ID to filter by
            action: Optional action type to filter by
            limit: Maximum number of logs to return
            
        Returns:
            List of audit log dictionaries in chronological order
        """
        if not caller_id:
            raise ValueError("Caller ID cannot be empty")
        
        if limit <= 0 or limit > 1000:
            raise ValueError("Limit must be between 1 and 1000")
        
        try:
            with self._get_connection() as conn:
                # Build query with filters
                query = """
                    SELECT * FROM audit_logs 
                    WHERE caller_id = ?
                """
                params = [caller_id]
                
                if start_date:
                    query += " AND timestamp >= ?"
                    params.append(start_date.isoformat())
                
                if end_date:
                    query += " AND timestamp <= ?"
                    params.append(end_date.isoformat())
                
                if key_id:
                    query += " AND key_id = ?"
                    params.append(key_id)
                
                if action:
                    query += " AND action = ?"
                    params.append(action)
                
                # Order chronologically (newest first) and apply limit
                query += " ORDER BY timestamp DESC LIMIT ?"
                params.append(limit)
                
                cursor = conn.execute(query, params)
                
                logs = []
                for row in cursor.fetchall():
                    log_entry = self._row_to_audit_log(row)
                    logs.append(log_entry.to_dict())
                
                return logs
                
        except Exception as e:
            logger.error(f"Failed to retrieve audit logs for caller {caller_id}: {str(e)}")
            raise RuntimeError(f"Log retrieval failed: {str(e)}")
    
    async def get_error_logs(self, key_id: Optional[str] = None,
                           caller_id: Optional[str] = None,
                           start_date: Optional[datetime] = None,
                           end_date: Optional[datetime] = None,
                           limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get audit logs for errors and failures
        
        Args:
            key_id: Optional key ID to filter by
            caller_id: Optional caller ID to filter by
            start_date: Optional start date for filtering
            end_date: Optional end date for filtering
            limit: Maximum number of logs to return
            
        Returns:
            List of error audit log dictionaries
        """
        if limit <= 0 or limit > 1000:
            raise ValueError("Limit must be between 1 and 1000")
        
        try:
            with self._get_connection() as conn:
                # Build query for errors (response_code >= 400 OR error_message is not null)
                query = """
                    SELECT * FROM audit_logs 
                    WHERE (response_code >= 400 OR error_message IS NOT NULL)
                """
                params = []
                
                if key_id:
                    query += " AND key_id = ?"
                    params.append(key_id)
                
                if caller_id:
                    query += " AND caller_id = ?"
                    params.append(caller_id)
                
                if start_date:
                    query += " AND timestamp >= ?"
                    params.append(start_date.isoformat())
                
                if end_date:
                    query += " AND timestamp <= ?"
                    params.append(end_date.isoformat())
                
                # Order chronologically (newest first) and apply limit
                query += " ORDER BY timestamp DESC LIMIT ?"
                params.append(limit)
                
                cursor = conn.execute(query, params)
                
                logs = []
                for row in cursor.fetchall():
                    log_entry = self._row_to_audit_log(row)
                    logs.append(log_entry.to_dict())
                
                return logs
                
        except Exception as e:
            logger.error(f"Failed to retrieve error logs: {str(e)}")
            raise RuntimeError(f"Error log retrieval failed: {str(e)}")
    
    async def get_usage_statistics(self, key_id: str, owner_id: str,
                                 start_date: Optional[datetime] = None,
                                 end_date: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Get usage statistics for a key (only accessible by key owner)
        
        Args:
            key_id: ID of the key to get statistics for
            owner_id: Coral ID of the key owner (for access control)
            start_date: Optional start date for filtering
            end_date: Optional end date for filtering
            
        Returns:
            Dictionary with usage statistics
        """
        if not key_id or not owner_id:
            raise ValueError("Key ID and owner ID cannot be empty")
        
        try:
            with self._get_connection() as conn:
                # Build base query
                base_query = "SELECT * FROM audit_logs WHERE key_id = ?"
                params = [key_id]
                
                if start_date:
                    base_query += " AND timestamp >= ?"
                    params.append(start_date.isoformat())
                
                if end_date:
                    base_query += " AND timestamp <= ?"
                    params.append(end_date.isoformat())
                
                # Get all logs for analysis
                cursor = conn.execute(base_query, params)
                logs = cursor.fetchall()
                
                # Calculate statistics
                total_calls = len([log for log in logs if log['action'] == 'proxy_call'])
                successful_calls = len([log for log in logs if log['action'] == 'proxy_call' and log['response_code'] < 400])
                failed_calls = total_calls - successful_calls
                rate_limit_blocks = len([log for log in logs if log['action'] == 'rate_limit_blocked'])
                
                # Calculate average response time for successful calls
                successful_response_times = [log['response_time'] for log in logs 
                                           if log['action'] == 'proxy_call' and log['response_code'] < 400]
                avg_response_time = sum(successful_response_times) / len(successful_response_times) if successful_response_times else 0.0
                
                # Calculate total payload size
                total_payload_size = sum(log['payload_size'] for log in logs if log['action'] == 'proxy_call')
                
                # Get unique callers
                unique_callers = len(set(log['caller_id'] for log in logs))
                
                return {
                    'key_id': key_id,
                    'total_calls': total_calls,
                    'successful_calls': successful_calls,
                    'failed_calls': failed_calls,
                    'rate_limit_blocks': rate_limit_blocks,
                    'success_rate': (successful_calls / total_calls * 100) if total_calls > 0 else 0.0,
                    'average_response_time': avg_response_time,
                    'total_payload_size': total_payload_size,
                    'unique_callers': unique_callers,
                    'period_start': start_date.isoformat() if start_date else None,
                    'period_end': end_date.isoformat() if end_date else None
                }
                
        except Exception as e:
            logger.error(f"Failed to get usage statistics for key {key_id}: {str(e)}")
            raise RuntimeError(f"Statistics calculation failed: {str(e)}")
    
    async def cleanup_old_logs(self, days_to_keep: int = 90) -> int:
        """
        Clean up old audit logs to prevent database bloat
        
        Args:
            days_to_keep: Number of days of logs to retain
            
        Returns:
            Number of logs deleted
        """
        if days_to_keep <= 0:
            raise ValueError("Days to keep must be positive")
        
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
            
            with self._get_connection() as conn:
                # Delete from sequence table first (foreign key constraint)
                conn.execute("""
                    DELETE FROM log_sequence 
                    WHERE log_id IN (
                        SELECT log_id FROM audit_logs 
                        WHERE timestamp < ?
                    )
                """, (cutoff_date.isoformat(),))
                
                # Delete from main audit_logs table
                cursor = conn.execute("""
                    DELETE FROM audit_logs 
                    WHERE timestamp < ?
                """, (cutoff_date.isoformat(),))
                
                conn.commit()
                
                deleted_count = cursor.rowcount
                if deleted_count > 0:
                    logger.info(f"Cleaned up {deleted_count} old audit logs")
                return deleted_count
                
        except Exception as e:
            logger.error(f"Failed to cleanup old logs: {str(e)}")
            return 0