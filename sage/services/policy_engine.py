"""
Policy Engine for Sage - handles rate limiting and usage policy enforcement
"""

import sqlite3
import os
from datetime import datetime, date, timedelta
from typing import Dict, Any, Optional, List
from contextlib import contextmanager
import logging
import json

from ..models.usage_counter import UsageCounter
from ..models.access_grant import AccessGrant


logger = logging.getLogger(__name__)


class PolicyEngine:
    """
    Policy engine that enforces rate limits and usage policies
    Handles usage tracking, rate limit enforcement, and daily counter resets
    """
    
    def __init__(self, db_path: str = "sage_policy.db"):
        """
        Initialize policy engine with SQLite storage
        
        Args:
            db_path: Path to SQLite database file for usage tracking
        """
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self) -> None:
        """Initialize SQLite database with required tables"""
        with self._get_connection() as conn:
            # Usage counters table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS usage_counters (
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
            
            # Create indexes for better query performance
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_usage_date 
                ON usage_counters(date)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_usage_key_caller 
                ON usage_counters(key_id, caller_id)
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
    
    def _row_to_usage_counter(self, row) -> UsageCounter:
        """Convert database row to UsageCounter instance"""
        return UsageCounter(
            key_id=row['key_id'],
            caller_id=row['caller_id'],
            date=date.fromisoformat(row['date']),
            call_count=row['call_count'],
            total_payload_size=row['total_payload_size'],
            average_response_time=row['average_response_time'],
            last_reset=datetime.fromisoformat(row['last_reset'])
        )
    
    async def check_rate_limit(self, key_id: str, caller_id: str, grant: AccessGrant) -> bool:
        """
        Check if a caller has exceeded their rate limit for a specific key
        
        Args:
            key_id: ID of the key being accessed
            caller_id: Coral ID of the caller
            grant: AccessGrant containing rate limit permissions
            
        Returns:
            True if within rate limit, False if exceeded
        """
        if not key_id or not caller_id or not grant:
            logger.warning("Invalid parameters for rate limit check")
            return False
        
        try:
            max_calls = grant.get_max_calls_per_day()
            if max_calls <= 0:
                logger.warning(f"Invalid max_calls_per_day: {max_calls}")
                return False
            
            # Get current usage for today
            current_usage = await self.get_current_usage(key_id, caller_id)
            
            # Check if within limit
            within_limit = current_usage < max_calls
            
            if not within_limit:
                logger.info(f"Rate limit exceeded for caller {caller_id} on key {key_id}: "
                           f"{current_usage}/{max_calls}")
            
            return within_limit
            
        except Exception as e:
            logger.error(f"Failed to check rate limit for caller {caller_id} on key {key_id}: {str(e)}")
            return False
    
    async def increment_usage(self, key_id: str, caller_id: str, payload_size: int = 0, 
                            response_time: float = 0.0) -> None:
        """
        Increment usage counter for a caller and key combination
        
        Args:
            key_id: ID of the key being used
            caller_id: Coral ID of the caller
            payload_size: Size of the request payload in bytes
            response_time: Response time in milliseconds
        """
        if not key_id or not caller_id:
            logger.warning("Invalid parameters for usage increment")
            return
        
        try:
            today = date.today()
            
            with self._get_connection() as conn:
                # Try to get existing counter for today
                cursor = conn.execute("""
                    SELECT * FROM usage_counters 
                    WHERE key_id = ? AND caller_id = ? AND date = ?
                """, (key_id, caller_id, today.isoformat()))
                row = cursor.fetchone()
                
                if row:
                    # Update existing counter
                    counter = self._row_to_usage_counter(row)
                    counter.increment_usage(payload_size, response_time)
                    
                    conn.execute("""
                        UPDATE usage_counters 
                        SET call_count = ?, total_payload_size = ?, average_response_time = ?
                        WHERE key_id = ? AND caller_id = ? AND date = ?
                    """, (
                        counter.call_count,
                        counter.total_payload_size,
                        counter.average_response_time,
                        key_id,
                        caller_id,
                        today.isoformat()
                    ))
                else:
                    # Create new counter
                    counter = UsageCounter.create_new(key_id, caller_id, today)
                    counter.increment_usage(payload_size, response_time)
                    
                    conn.execute("""
                        INSERT INTO usage_counters 
                        (key_id, caller_id, date, call_count, total_payload_size, 
                         average_response_time, last_reset)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        counter.key_id,
                        counter.caller_id,
                        counter.date.isoformat(),
                        counter.call_count,
                        counter.total_payload_size,
                        counter.average_response_time,
                        counter.last_reset.isoformat()
                    ))
                
                conn.commit()
                logger.debug(f"Incremented usage for caller {caller_id} on key {key_id}")
                
        except Exception as e:
            logger.error(f"Failed to increment usage for caller {caller_id} on key {key_id}: {str(e)}")
    
    async def get_current_usage(self, key_id: str, caller_id: str, target_date: date = None) -> int:
        """
        Get current usage count for a caller and key combination
        
        Args:
            key_id: ID of the key
            caller_id: Coral ID of the caller
            target_date: Date to check usage for (defaults to today)
            
        Returns:
            Current call count for the specified date
        """
        if not key_id or not caller_id:
            return 0
        
        if target_date is None:
            target_date = date.today()
        
        try:
            with self._get_connection() as conn:
                cursor = conn.execute("""
                    SELECT call_count FROM usage_counters 
                    WHERE key_id = ? AND caller_id = ? AND date = ?
                """, (key_id, caller_id, target_date.isoformat()))
                row = cursor.fetchone()
                
                return row['call_count'] if row else 0
                
        except Exception as e:
            logger.error(f"Failed to get current usage for caller {caller_id} on key {key_id}: {str(e)}")
            return 0
    
    async def reset_daily_counters(self, target_date: date = None) -> int:
        """
        Reset daily counters for a specific date (used for cleanup)
        
        Args:
            target_date: Date to reset counters for (defaults to today)
            
        Returns:
            Number of counters reset
        """
        if target_date is None:
            target_date = date.today()
        
        try:
            reset_time = datetime.utcnow()
            
            with self._get_connection() as conn:
                cursor = conn.execute("""
                    UPDATE usage_counters 
                    SET call_count = 0, total_payload_size = 0, 
                        average_response_time = 0.0, last_reset = ?
                    WHERE date = ?
                """, (reset_time.isoformat(), target_date.isoformat()))
                conn.commit()
                
                reset_count = cursor.rowcount
                if reset_count > 0:
                    logger.info(f"Reset {reset_count} daily counters for {target_date}")
                return reset_count
                
        except Exception as e:
            logger.error(f"Failed to reset daily counters for {target_date}: {str(e)}")
            return 0
    
    async def cleanup_old_counters(self, days_to_keep: int = 30) -> int:
        """
        Clean up old usage counters to prevent database bloat
        
        Args:
            days_to_keep: Number of days of history to retain
            
        Returns:
            Number of counters deleted
        """
        try:
            cutoff_date = date.today() - timedelta(days=days_to_keep)
            
            with self._get_connection() as conn:
                cursor = conn.execute("""
                    DELETE FROM usage_counters 
                    WHERE date < ?
                """, (cutoff_date.isoformat(),))
                conn.commit()
                
                deleted_count = cursor.rowcount
                if deleted_count > 0:
                    logger.info(f"Cleaned up {deleted_count} old usage counters")
                return deleted_count
                
        except Exception as e:
            logger.error(f"Failed to cleanup old counters: {str(e)}")
            return 0
    
    async def update_policy(self, key_id: str, policy: Dict[str, Any], owner_id: str) -> bool:
        """
        Update policy for a specific key (placeholder for future policy storage)
        For MVP, policies are stored in AccessGrant permissions
        
        Args:
            key_id: ID of the key
            policy: New policy settings
            owner_id: Coral ID of the key owner
            
        Returns:
            True if update successful, False otherwise
        """
        # For MVP, this is a placeholder since policies are stored in grants
        # In future versions, this could store key-level policies
        logger.info(f"Policy update requested for key {key_id} by owner {owner_id}")
        return True
    
    async def get_usage_stats(self, key_id: str, caller_id: str = None, 
                            start_date: date = None, end_date: date = None) -> List[Dict[str, Any]]:
        """
        Get usage statistics for a key, optionally filtered by caller and date range
        
        Args:
            key_id: ID of the key
            caller_id: Optional caller ID to filter by
            start_date: Optional start date for range
            end_date: Optional end date for range
            
        Returns:
            List of usage statistics dictionaries
        """
        if not key_id:
            return []
        
        try:
            with self._get_connection() as conn:
                # Build query based on filters
                query = "SELECT * FROM usage_counters WHERE key_id = ?"
                params = [key_id]
                
                if caller_id:
                    query += " AND caller_id = ?"
                    params.append(caller_id)
                
                if start_date:
                    query += " AND date >= ?"
                    params.append(start_date.isoformat())
                
                if end_date:
                    query += " AND date <= ?"
                    params.append(end_date.isoformat())
                
                query += " ORDER BY date DESC, caller_id"
                
                cursor = conn.execute(query, params)
                
                stats = []
                for row in cursor.fetchall():
                    counter = self._row_to_usage_counter(row)
                    stats.append(counter.get_usage_summary())
                
                return stats
                
        except Exception as e:
            logger.error(f"Failed to get usage stats for key {key_id}: {str(e)}")
            return []
    
    async def get_rate_limit_status(self, key_id: str, caller_id: str, grant: AccessGrant) -> Dict[str, Any]:
        """
        Get detailed rate limit status for a caller and key
        
        Args:
            key_id: ID of the key
            caller_id: Coral ID of the caller
            grant: AccessGrant containing rate limit permissions
            
        Returns:
            Dictionary with rate limit status information
        """
        try:
            max_calls = grant.get_max_calls_per_day()
            current_usage = await self.get_current_usage(key_id, caller_id)
            remaining_calls = max(0, max_calls - current_usage)
            
            return {
                'key_id': key_id,
                'caller_id': caller_id,
                'max_calls_per_day': max_calls,
                'current_usage': current_usage,
                'remaining_calls': remaining_calls,
                'rate_limit_exceeded': current_usage >= max_calls,
                'reset_time': datetime.combine(date.today() + timedelta(days=1), datetime.min.time()).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get rate limit status for caller {caller_id} on key {key_id}: {str(e)}")
            return {
                'key_id': key_id,
                'caller_id': caller_id,
                'error': str(e)
            }