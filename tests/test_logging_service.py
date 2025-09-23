"""
Unit tests for LoggingService - privacy-aware audit logging
"""

import pytest
import asyncio
import os
import tempfile
from datetime import datetime, timedelta
from unittest.mock import patch

from sage.services.logging_service import LoggingService
from sage.models.privacy_audit_log import PrivacyAuditLog


class TestLoggingService:
    """Test suite for LoggingService functionality"""
    
    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing"""
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        yield path
        try:
            os.unlink(path)
        except OSError:
            pass
    
    @pytest.fixture
    def logging_service(self, temp_db):
        """Create LoggingService instance with temporary database"""
        return LoggingService(db_path=temp_db)
    
    @pytest.mark.asyncio
    async def test_database_initialization(self, logging_service):
        """Test that database is properly initialized"""
        # Database should be created and accessible
        assert os.path.exists(logging_service.db_path)
        
        # Should be able to query the tables
        with logging_service._get_connection() as conn:
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            assert 'audit_logs' in tables
            assert 'log_sequence' in tables
    
    @pytest.mark.asyncio
    async def test_log_proxy_call_success(self, logging_service):
        """Test logging a successful proxy call"""
        caller_id = "caller-123"
        key_id = "key-456"
        method = "POST"
        endpoint = "/api/v1/chat/completions"
        payload_size = 1024
        response_time = 250.5
        response_code = 200
        
        # Log the proxy call
        log_id = await logging_service.log_proxy_call(
            caller_id=caller_id,
            key_id=key_id,
            method=method,
            endpoint=endpoint,
            payload_size=payload_size,
            response_time=response_time,
            response_code=response_code
        )
        
        # Verify log was created
        assert log_id is not None
        assert isinstance(log_id, str)
        
        # Verify log can be retrieved
        logs = await logging_service.get_logs_for_key(key_id, "owner-123")
        assert len(logs) == 1
        
        log = logs[0]
        assert log['caller_id'] == caller_id
        assert log['key_id'] == key_id
        assert log['action'] == 'proxy_call'
        assert log['method'] == method
        assert log['endpoint'] == endpoint
        assert log['payload_size'] == payload_size
        assert log['response_time'] == response_time
        assert log['response_code'] == response_code
        assert log['error_message'] is None
    
    @pytest.mark.asyncio
    async def test_log_proxy_call_with_error(self, logging_service):
        """Test logging a proxy call with error"""
        caller_id = "caller-123"
        key_id = "key-456"
        method = "POST"
        endpoint = "/api/v1/chat/completions"
        payload_size = 512
        response_time = 100.0
        response_code = 500
        error_message = "Internal server error"
        
        # Log the proxy call with error
        log_id = await logging_service.log_proxy_call(
            caller_id=caller_id,
            key_id=key_id,
            method=method,
            endpoint=endpoint,
            payload_size=payload_size,
            response_time=response_time,
            response_code=response_code,
            error_message=error_message
        )
        
        # Verify log was created with error
        logs = await logging_service.get_logs_for_key(key_id, "owner-123")
        assert len(logs) == 1
        
        log = logs[0]
        assert log['response_code'] == response_code
        assert log['error_message'] == error_message
    
    @pytest.mark.asyncio
    async def test_log_grant_access(self, logging_service):
        """Test logging an access grant operation"""
        caller_id = "owner-123"
        key_id = "key-456"
        granted_to = "caller-789"
        permissions = {"max_calls_per_day": 100}
        
        # Log the grant access
        log_id = await logging_service.log_grant_access(
            caller_id=caller_id,
            key_id=key_id,
            granted_to=granted_to,
            permissions=permissions
        )
        
        # Verify log was created
        logs = await logging_service.get_logs_for_key(key_id, caller_id)
        assert len(logs) == 1
        
        log = logs[0]
        assert log['caller_id'] == caller_id
        assert log['key_id'] == key_id
        assert log['action'] == 'grant_access'
        assert log['method'] == 'POST'
        assert log['endpoint'] == f'/grant/{granted_to}'
        assert log['response_code'] == 200
    
    @pytest.mark.asyncio
    async def test_log_rate_limit_blocked(self, logging_service):
        """Test logging a rate limit blocked attempt"""
        caller_id = "caller-123"
        key_id = "key-456"
        method = "POST"
        endpoint = "/api/v1/chat/completions"
        current_usage = 101
        limit = 100
        
        # Log the rate limit block
        log_id = await logging_service.log_rate_limit_blocked(
            caller_id=caller_id,
            key_id=key_id,
            method=method,
            endpoint=endpoint,
            current_usage=current_usage,
            limit=limit
        )
        
        # Verify log was created
        logs = await logging_service.get_logs_for_key(key_id, "owner-123")
        assert len(logs) == 1
        
        log = logs[0]
        assert log['caller_id'] == caller_id
        assert log['key_id'] == key_id
        assert log['action'] == 'rate_limit_blocked'
        assert log['method'] == method
        assert log['endpoint'] == endpoint
        assert log['response_code'] == 429
        assert f"{current_usage}/{limit}" in log['error_message']
    
    @pytest.mark.asyncio
    async def test_log_authorization_failed(self, logging_service):
        """Test logging an authorization failure"""
        caller_id = "caller-123"
        key_id = "key-456"
        method = "POST"
        endpoint = "/api/v1/chat/completions"
        reason = "Grant expired"
        
        # Log the authorization failure
        log_id = await logging_service.log_authorization_failed(
            caller_id=caller_id,
            key_id=key_id,
            method=method,
            endpoint=endpoint,
            reason=reason
        )
        
        # Verify log was created
        logs = await logging_service.get_logs_for_key(key_id, "owner-123")
        assert len(logs) == 1
        
        log = logs[0]
        assert log['caller_id'] == caller_id
        assert log['key_id'] == key_id
        assert log['action'] == 'authorization_failed'
        assert log['method'] == method
        assert log['endpoint'] == endpoint
        assert log['response_code'] == 403
        assert log['error_message'] == reason
    
    @pytest.mark.asyncio
    async def test_get_logs_for_key_with_filters(self, logging_service):
        """Test retrieving logs for a key with various filters"""
        key_id = "key-456"
        owner_id = "owner-123"
        caller1 = "caller-111"
        caller2 = "caller-222"
        
        # Create multiple log entries
        await logging_service.log_proxy_call(caller1, key_id, "GET", "/api/v1/models", 0, 50.0, 200)
        await logging_service.log_proxy_call(caller2, key_id, "POST", "/api/v1/chat", 1024, 200.0, 200)
        await logging_service.log_rate_limit_blocked(caller1, key_id, "POST", "/api/v1/chat", 101, 100)
        
        # Get all logs
        all_logs = await logging_service.get_logs_for_key(key_id, owner_id)
        assert len(all_logs) == 3
        
        # Filter by caller
        caller1_logs = await logging_service.get_logs_for_key(key_id, owner_id, caller_id=caller1)
        assert len(caller1_logs) == 2
        assert all(log['caller_id'] == caller1 for log in caller1_logs)
        
        # Filter by action
        proxy_logs = await logging_service.get_logs_for_key(key_id, owner_id, action="proxy_call")
        assert len(proxy_logs) == 2
        assert all(log['action'] == 'proxy_call' for log in proxy_logs)
        
        # Test limit
        limited_logs = await logging_service.get_logs_for_key(key_id, owner_id, limit=1)
        assert len(limited_logs) == 1
    
    @pytest.mark.asyncio
    async def test_get_logs_for_key_with_date_range(self, logging_service):
        """Test retrieving logs with date range filtering"""
        key_id = "key-456"
        owner_id = "owner-123"
        
        # Create log entry
        await logging_service.log_proxy_call("caller-123", key_id, "GET", "/api/v1/models", 0, 50.0, 200)
        
        # Test date range filtering
        now = datetime.utcnow()
        start_date = now - timedelta(hours=1)
        end_date = now + timedelta(hours=1)
        
        # Should find the log within range
        logs_in_range = await logging_service.get_logs_for_key(
            key_id, owner_id, start_date=start_date, end_date=end_date
        )
        assert len(logs_in_range) == 1
        
        # Should not find logs outside range
        old_start = now - timedelta(days=2)
        old_end = now - timedelta(days=1)
        
        logs_out_of_range = await logging_service.get_logs_for_key(
            key_id, owner_id, start_date=old_start, end_date=old_end
        )
        assert len(logs_out_of_range) == 0
    
    @pytest.mark.asyncio
    async def test_get_logs_by_caller(self, logging_service):
        """Test retrieving logs by caller across multiple keys"""
        caller_id = "caller-123"
        key1 = "key-111"
        key2 = "key-222"
        
        # Create logs for different keys
        await logging_service.log_proxy_call(caller_id, key1, "GET", "/api/v1/models", 0, 50.0, 200)
        await logging_service.log_proxy_call(caller_id, key2, "POST", "/api/v1/chat", 1024, 200.0, 200)
        await logging_service.log_proxy_call("other-caller", key1, "GET", "/api/v1/models", 0, 75.0, 200)
        
        # Get logs for specific caller
        caller_logs = await logging_service.get_logs_by_caller(caller_id)
        assert len(caller_logs) == 2
        assert all(log['caller_id'] == caller_id for log in caller_logs)
        
        # Filter by key
        key1_logs = await logging_service.get_logs_by_caller(caller_id, key_id=key1)
        assert len(key1_logs) == 1
        assert key1_logs[0]['key_id'] == key1
    
    @pytest.mark.asyncio
    async def test_get_error_logs(self, logging_service):
        """Test retrieving error logs"""
        key_id = "key-456"
        caller_id = "caller-123"
        
        # Create successful and error logs
        await logging_service.log_proxy_call(caller_id, key_id, "GET", "/api/v1/models", 0, 50.0, 200)
        await logging_service.log_proxy_call(caller_id, key_id, "POST", "/api/v1/chat", 1024, 200.0, 500, "Server error")
        await logging_service.log_rate_limit_blocked(caller_id, key_id, "POST", "/api/v1/chat", 101, 100)
        await logging_service.log_authorization_failed(caller_id, key_id, "GET", "/api/v1/models", "No permission")
        
        # Get all error logs
        error_logs = await logging_service.get_error_logs()
        assert len(error_logs) == 3  # 500 error, rate limit (429), auth failure (403)
        
        # Verify all are errors
        for log in error_logs:
            assert log['response_code'] >= 400 or log['error_message'] is not None
        
        # Filter error logs by key
        key_error_logs = await logging_service.get_error_logs(key_id=key_id)
        assert len(key_error_logs) == 3
        assert all(log['key_id'] == key_id for log in key_error_logs)
    
    @pytest.mark.asyncio
    async def test_get_usage_statistics(self, logging_service):
        """Test getting usage statistics for a key"""
        key_id = "key-456"
        owner_id = "owner-123"
        caller1 = "caller-111"
        caller2 = "caller-222"
        
        # Create various log entries
        await logging_service.log_proxy_call(caller1, key_id, "GET", "/api/v1/models", 100, 50.0, 200)
        await logging_service.log_proxy_call(caller1, key_id, "POST", "/api/v1/chat", 1024, 200.0, 200)
        await logging_service.log_proxy_call(caller2, key_id, "POST", "/api/v1/chat", 512, 150.0, 500, "Error")
        await logging_service.log_rate_limit_blocked(caller1, key_id, "POST", "/api/v1/chat", 101, 100)
        await logging_service.log_grant_access(owner_id, key_id, caller2, {"max_calls_per_day": 50})
        
        # Get usage statistics
        stats = await logging_service.get_usage_statistics(key_id, owner_id)
        
        assert stats['key_id'] == key_id
        assert stats['total_calls'] == 3  # Only proxy_call actions
        assert stats['successful_calls'] == 2  # 200 status codes
        assert stats['failed_calls'] == 1  # 500 status code
        assert stats['rate_limit_blocks'] == 1
        assert stats['success_rate'] == 2/3 * 100  # 66.67%
        assert stats['average_response_time'] == (50.0 + 200.0) / 2  # Average of successful calls
        assert stats['total_payload_size'] == 100 + 1024 + 512  # Sum of all proxy call payloads
        assert stats['unique_callers'] == 3  # caller1, caller2, owner_id
    
    @pytest.mark.asyncio
    async def test_chronological_ordering(self, logging_service):
        """Test that logs are stored and retrieved in chronological order"""
        key_id = "key-456"
        owner_id = "owner-123"
        caller_id = "caller-123"
        
        # Create logs with small delays to ensure different timestamps
        log1_id = await logging_service.log_proxy_call(caller_id, key_id, "GET", "/api/v1/models", 0, 50.0, 200)
        
        # Small delay to ensure different timestamp
        await asyncio.sleep(0.01)
        
        log2_id = await logging_service.log_proxy_call(caller_id, key_id, "POST", "/api/v1/chat", 1024, 200.0, 200)
        
        await asyncio.sleep(0.01)
        
        log3_id = await logging_service.log_rate_limit_blocked(caller_id, key_id, "POST", "/api/v1/chat", 101, 100)
        
        # Retrieve logs (should be in reverse chronological order - newest first)
        logs = await logging_service.get_logs_for_key(key_id, owner_id)
        assert len(logs) == 3
        
        # Verify chronological ordering (newest first)
        assert logs[0]['log_id'] == log3_id  # Most recent
        assert logs[1]['log_id'] == log2_id  # Middle
        assert logs[2]['log_id'] == log1_id  # Oldest
        
        # Verify timestamps are in descending order
        timestamp1 = datetime.fromisoformat(logs[0]['timestamp'])
        timestamp2 = datetime.fromisoformat(logs[1]['timestamp'])
        timestamp3 = datetime.fromisoformat(logs[2]['timestamp'])
        
        assert timestamp1 >= timestamp2 >= timestamp3
    
    @pytest.mark.asyncio
    async def test_tamper_resistant_storage(self, logging_service):
        """Test that logs are stored in tamper-resistant manner"""
        key_id = "key-456"
        caller_id = "caller-123"
        
        # Create a log entry
        log_id = await logging_service.log_proxy_call(caller_id, key_id, "GET", "/api/v1/models", 0, 50.0, 200)
        
        # Verify log exists in both tables
        with logging_service._get_connection() as conn:
            # Check main audit_logs table
            cursor = conn.execute("SELECT COUNT(*) FROM audit_logs WHERE log_id = ?", (log_id,))
            assert cursor.fetchone()[0] == 1
            
            # Check sequence table
            cursor = conn.execute("SELECT COUNT(*) FROM log_sequence WHERE log_id = ?", (log_id,))
            assert cursor.fetchone()[0] == 1
    
    @pytest.mark.asyncio
    async def test_cleanup_old_logs(self, logging_service):
        """Test cleaning up old audit logs"""
        key_id = "key-456"
        caller_id = "caller-123"
        
        # Create a log entry
        await logging_service.log_proxy_call(caller_id, key_id, "GET", "/api/v1/models", 0, 50.0, 200)
        
        # Manually update timestamp to make it old
        old_timestamp = (datetime.utcnow() - timedelta(days=100)).isoformat()
        with logging_service._get_connection() as conn:
            conn.execute("UPDATE audit_logs SET timestamp = ? WHERE key_id = ?", (old_timestamp, key_id))
            conn.commit()
        
        # Verify log exists
        logs = await logging_service.get_logs_for_key(key_id, "owner-123")
        assert len(logs) == 1
        
        # Cleanup old logs (keep 30 days)
        deleted_count = await logging_service.cleanup_old_logs(days_to_keep=30)
        assert deleted_count == 1
        
        # Verify log was deleted
        logs = await logging_service.get_logs_for_key(key_id, "owner-123")
        assert len(logs) == 0
    
    @pytest.mark.asyncio
    async def test_input_validation(self, logging_service):
        """Test input validation for logging methods"""
        # Test empty caller_id
        with pytest.raises(ValueError, match="Caller ID cannot be empty"):
            await logging_service.log_proxy_call("", "key-123", "GET", "/api", 0, 0.0, 200)
        
        # Test empty key_id
        with pytest.raises(ValueError, match="Key ID cannot be empty"):
            await logging_service.log_proxy_call("caller-123", "", "GET", "/api", 0, 0.0, 200)
        
        # Test negative payload_size
        with pytest.raises(ValueError, match="Payload size cannot be negative"):
            await logging_service.log_proxy_call("caller-123", "key-123", "GET", "/api", -1, 0.0, 200)
        
        # Test negative response_time
        with pytest.raises(ValueError, match="Response time cannot be negative"):
            await logging_service.log_proxy_call("caller-123", "key-123", "GET", "/api", 0, -1.0, 200)
        
        # Test invalid limit in get_logs_for_key
        with pytest.raises(ValueError, match="Limit must be between 1 and 1000"):
            await logging_service.get_logs_for_key("key-123", "owner-123", limit=0)
        
        with pytest.raises(ValueError, match="Limit must be between 1 and 1000"):
            await logging_service.get_logs_for_key("key-123", "owner-123", limit=1001)
    
    @pytest.mark.asyncio
    async def test_privacy_protection(self, logging_service):
        """Test that sensitive payload content is not logged"""
        key_id = "key-456"
        caller_id = "caller-123"
        method = "POST"
        endpoint = "/api/v1/chat/completions"
        payload_size = 1024  # Only size, not content
        
        # Log a proxy call
        await logging_service.log_proxy_call(
            caller_id=caller_id,
            key_id=key_id,
            method=method,
            endpoint=endpoint,
            payload_size=payload_size,
            response_time=200.0,
            response_code=200
        )
        
        # Retrieve and verify only metadata is stored
        logs = await logging_service.get_logs_for_key(key_id, "owner-123")
        assert len(logs) == 1
        
        log = logs[0]
        # Verify we only have metadata, no sensitive content
        assert 'payload_content' not in log
        assert 'response_content' not in log
        assert 'api_key' not in log
        assert log['payload_size'] == payload_size  # Only size is logged
        
        # Verify all expected metadata fields are present
        expected_fields = [
            'log_id', 'timestamp', 'caller_id', 'key_id', 'action',
            'method', 'endpoint', 'payload_size', 'response_time', 'response_code'
        ]
        for field in expected_fields:
            assert field in log


if __name__ == "__main__":
    pytest.main([__file__])