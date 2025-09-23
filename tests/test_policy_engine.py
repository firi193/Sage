"""
Unit tests for PolicyEngine - rate limiting and usage policy enforcement
"""

import pytest
import asyncio
import os
import tempfile
from datetime import datetime, date, timedelta
from unittest.mock import patch

from sage.services.policy_engine import PolicyEngine
from sage.models.access_grant import AccessGrant
from sage.models.usage_counter import UsageCounter


class TestPolicyEngine:
    """Test suite for PolicyEngine functionality"""
    
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
    def policy_engine(self, temp_db):
        """Create PolicyEngine instance with temporary database"""
        return PolicyEngine(db_path=temp_db)
    
    @pytest.fixture
    def sample_grant(self):
        """Create a sample AccessGrant for testing"""
        return AccessGrant.create_new(
            key_id="test-key-123",
            caller_id="caller-456",
            permissions={"max_calls_per_day": 100},
            expires_at=datetime.utcnow() + timedelta(hours=24),
            granted_by="owner-789"
        )
    
    @pytest.mark.asyncio
    async def test_database_initialization(self, policy_engine):
        """Test that database is properly initialized"""
        # Database should be created and accessible
        assert os.path.exists(policy_engine.db_path)
        
        # Should be able to query the tables
        with policy_engine._get_connection() as conn:
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            assert 'usage_counters' in tables
    
    @pytest.mark.asyncio
    async def test_increment_usage_new_counter(self, policy_engine):
        """Test incrementing usage creates new counter"""
        key_id = "test-key-123"
        caller_id = "caller-456"
        payload_size = 1024
        response_time = 150.5
        
        # Increment usage
        await policy_engine.increment_usage(key_id, caller_id, payload_size, response_time)
        
        # Verify counter was created
        usage = await policy_engine.get_current_usage(key_id, caller_id)
        assert usage == 1
        
        # Verify stats
        stats = await policy_engine.get_usage_stats(key_id, caller_id)
        assert len(stats) == 1
        assert stats[0]['call_count'] == 1
        assert stats[0]['total_payload_size'] == payload_size
        assert stats[0]['average_response_time'] == response_time
    
    @pytest.mark.asyncio
    async def test_increment_usage_existing_counter(self, policy_engine):
        """Test incrementing usage updates existing counter"""
        key_id = "test-key-123"
        caller_id = "caller-456"
        
        # First increment
        await policy_engine.increment_usage(key_id, caller_id, 500, 100.0)
        
        # Second increment
        await policy_engine.increment_usage(key_id, caller_id, 300, 200.0)
        
        # Verify counter was updated
        usage = await policy_engine.get_current_usage(key_id, caller_id)
        assert usage == 2
        
        # Verify stats
        stats = await policy_engine.get_usage_stats(key_id, caller_id)
        assert len(stats) == 1
        assert stats[0]['call_count'] == 2
        assert stats[0]['total_payload_size'] == 800
        assert stats[0]['average_response_time'] == 150.0  # (100 + 200) / 2
    
    @pytest.mark.asyncio
    async def test_check_rate_limit_within_limit(self, policy_engine, sample_grant):
        """Test rate limit check when within limit"""
        key_id = sample_grant.key_id
        caller_id = sample_grant.caller_id
        
        # Use some calls but stay within limit
        for _ in range(50):  # 50 < 100 (limit)
            await policy_engine.increment_usage(key_id, caller_id)
        
        # Should be within limit
        within_limit = await policy_engine.check_rate_limit(key_id, caller_id, sample_grant)
        assert within_limit is True
    
    @pytest.mark.asyncio
    async def test_check_rate_limit_exceeded(self, policy_engine, sample_grant):
        """Test rate limit check when limit exceeded"""
        key_id = sample_grant.key_id
        caller_id = sample_grant.caller_id
        
        # Exceed the limit
        for _ in range(101):  # 101 > 100 (limit)
            await policy_engine.increment_usage(key_id, caller_id)
        
        # Should exceed limit
        within_limit = await policy_engine.check_rate_limit(key_id, caller_id, sample_grant)
        assert within_limit is False
    
    @pytest.mark.asyncio
    async def test_check_rate_limit_at_limit(self, policy_engine, sample_grant):
        """Test rate limit check when exactly at limit"""
        key_id = sample_grant.key_id
        caller_id = sample_grant.caller_id
        
        # Use exactly the limit
        for _ in range(100):  # 100 == 100 (limit)
            await policy_engine.increment_usage(key_id, caller_id)
        
        # Should be at limit (not within)
        within_limit = await policy_engine.check_rate_limit(key_id, caller_id, sample_grant)
        assert within_limit is False
    
    @pytest.mark.asyncio
    async def test_check_rate_limit_invalid_params(self, policy_engine, sample_grant):
        """Test rate limit check with invalid parameters"""
        # Empty key_id
        result = await policy_engine.check_rate_limit("", "caller", sample_grant)
        assert result is False
        
        # Empty caller_id
        result = await policy_engine.check_rate_limit("key", "", sample_grant)
        assert result is False
        
        # None grant
        result = await policy_engine.check_rate_limit("key", "caller", None)
        assert result is False
    
    @pytest.mark.asyncio
    async def test_check_rate_limit_invalid_grant_permissions(self, policy_engine):
        """Test rate limit check with invalid grant permissions"""
        # Grant with zero max calls
        grant = AccessGrant.create_new(
            key_id="test-key",
            caller_id="caller",
            permissions={"max_calls_per_day": 0},
            expires_at=datetime.utcnow() + timedelta(hours=24),
            granted_by="owner"
        )
        
        result = await policy_engine.check_rate_limit("test-key", "caller", grant)
        assert result is False
        
        # Grant with negative max calls
        grant.permissions["max_calls_per_day"] = -10
        result = await policy_engine.check_rate_limit("test-key", "caller", grant)
        assert result is False
    
    @pytest.mark.asyncio
    async def test_get_current_usage_no_usage(self, policy_engine):
        """Test getting current usage when no usage exists"""
        usage = await policy_engine.get_current_usage("nonexistent-key", "nonexistent-caller")
        assert usage == 0
    
    @pytest.mark.asyncio
    async def test_get_current_usage_with_date(self, policy_engine):
        """Test getting current usage for specific date"""
        key_id = "test-key-123"
        caller_id = "caller-456"
        yesterday = date.today() - timedelta(days=1)
        
        # Mock usage for yesterday
        with policy_engine._get_connection() as conn:
            conn.execute("""
                INSERT INTO usage_counters 
                (key_id, caller_id, date, call_count, total_payload_size, 
                 average_response_time, last_reset)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                key_id, caller_id, yesterday.isoformat(), 
                5, 1000, 100.0, datetime.utcnow().isoformat()
            ))
            conn.commit()
        
        # Get usage for yesterday
        usage = await policy_engine.get_current_usage(key_id, caller_id, yesterday)
        assert usage == 5
        
        # Get usage for today (should be 0)
        usage = await policy_engine.get_current_usage(key_id, caller_id)
        assert usage == 0
    
    @pytest.mark.asyncio
    async def test_reset_daily_counters(self, policy_engine):
        """Test resetting daily counters"""
        key_id = "test-key-123"
        caller_id = "caller-456"
        today = date.today()
        
        # Create some usage
        await policy_engine.increment_usage(key_id, caller_id, 500, 100.0)
        await policy_engine.increment_usage(key_id, caller_id, 300, 200.0)
        
        # Verify usage exists
        usage = await policy_engine.get_current_usage(key_id, caller_id)
        assert usage == 2
        
        # Reset counters
        reset_count = await policy_engine.reset_daily_counters(today)
        assert reset_count == 1
        
        # Verify usage is reset
        usage = await policy_engine.get_current_usage(key_id, caller_id)
        assert usage == 0
    
    @pytest.mark.asyncio
    async def test_cleanup_old_counters(self, policy_engine):
        """Test cleaning up old usage counters"""
        key_id = "test-key-123"
        caller_id = "caller-456"
        old_date = date.today() - timedelta(days=35)
        recent_date = date.today() - timedelta(days=5)
        
        # Create old and recent usage
        with policy_engine._get_connection() as conn:
            # Old usage (should be deleted)
            conn.execute("""
                INSERT INTO usage_counters 
                (key_id, caller_id, date, call_count, total_payload_size, 
                 average_response_time, last_reset)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                key_id, caller_id, old_date.isoformat(), 
                10, 2000, 150.0, datetime.utcnow().isoformat()
            ))
            
            # Recent usage (should be kept)
            conn.execute("""
                INSERT INTO usage_counters 
                (key_id, caller_id, date, call_count, total_payload_size, 
                 average_response_time, last_reset)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                key_id, caller_id, recent_date.isoformat(), 
                5, 1000, 100.0, datetime.utcnow().isoformat()
            ))
            conn.commit()
        
        # Cleanup old counters (keep 30 days)
        deleted_count = await policy_engine.cleanup_old_counters(days_to_keep=30)
        assert deleted_count == 1
        
        # Verify only recent usage remains
        stats = await policy_engine.get_usage_stats(key_id, caller_id)
        assert len(stats) == 1
        assert stats[0]['date'] == recent_date.isoformat()
    
    @pytest.mark.asyncio
    async def test_get_usage_stats_filtered(self, policy_engine):
        """Test getting usage statistics with filters"""
        key_id = "test-key-123"
        caller1 = "caller-456"
        caller2 = "caller-789"
        
        # Create usage for different callers and dates
        await policy_engine.increment_usage(key_id, caller1, 100, 50.0)
        await policy_engine.increment_usage(key_id, caller2, 200, 75.0)
        
        # Get all stats for key
        all_stats = await policy_engine.get_usage_stats(key_id)
        assert len(all_stats) == 2
        
        # Get stats filtered by caller
        caller1_stats = await policy_engine.get_usage_stats(key_id, caller_id=caller1)
        assert len(caller1_stats) == 1
        assert caller1_stats[0]['caller_id'] == caller1
        
        caller2_stats = await policy_engine.get_usage_stats(key_id, caller_id=caller2)
        assert len(caller2_stats) == 1
        assert caller2_stats[0]['caller_id'] == caller2
    
    @pytest.mark.asyncio
    async def test_get_usage_stats_date_range(self, policy_engine):
        """Test getting usage statistics with date range"""
        key_id = "test-key-123"
        caller_id = "caller-456"
        
        # Create usage for different dates
        yesterday = date.today() - timedelta(days=1)
        today = date.today()
        
        with policy_engine._get_connection() as conn:
            # Yesterday's usage
            conn.execute("""
                INSERT INTO usage_counters 
                (key_id, caller_id, date, call_count, total_payload_size, 
                 average_response_time, last_reset)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                key_id, caller_id, yesterday.isoformat(), 
                5, 1000, 100.0, datetime.utcnow().isoformat()
            ))
            
            # Today's usage
            conn.execute("""
                INSERT INTO usage_counters 
                (key_id, caller_id, date, call_count, total_payload_size, 
                 average_response_time, last_reset)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                key_id, caller_id, today.isoformat(), 
                3, 600, 80.0, datetime.utcnow().isoformat()
            ))
            conn.commit()
        
        # Get stats for today only
        today_stats = await policy_engine.get_usage_stats(
            key_id, caller_id, start_date=today, end_date=today
        )
        assert len(today_stats) == 1
        assert today_stats[0]['call_count'] == 3
        
        # Get stats for yesterday only
        yesterday_stats = await policy_engine.get_usage_stats(
            key_id, caller_id, start_date=yesterday, end_date=yesterday
        )
        assert len(yesterday_stats) == 1
        assert yesterday_stats[0]['call_count'] == 5
        
        # Get stats for both days
        all_stats = await policy_engine.get_usage_stats(
            key_id, caller_id, start_date=yesterday, end_date=today
        )
        assert len(all_stats) == 2
    
    @pytest.mark.asyncio
    async def test_get_rate_limit_status(self, policy_engine, sample_grant):
        """Test getting detailed rate limit status"""
        key_id = sample_grant.key_id
        caller_id = sample_grant.caller_id
        
        # Use some calls
        for _ in range(25):
            await policy_engine.increment_usage(key_id, caller_id)
        
        # Get rate limit status
        status = await policy_engine.get_rate_limit_status(key_id, caller_id, sample_grant)
        
        assert status['key_id'] == key_id
        assert status['caller_id'] == caller_id
        assert status['max_calls_per_day'] == 100
        assert status['current_usage'] == 25
        assert status['remaining_calls'] == 75
        assert status['rate_limit_exceeded'] is False
        assert 'reset_time' in status
    
    @pytest.mark.asyncio
    async def test_get_rate_limit_status_exceeded(self, policy_engine, sample_grant):
        """Test getting rate limit status when exceeded"""
        key_id = sample_grant.key_id
        caller_id = sample_grant.caller_id
        
        # Exceed the limit
        for _ in range(150):
            await policy_engine.increment_usage(key_id, caller_id)
        
        # Get rate limit status
        status = await policy_engine.get_rate_limit_status(key_id, caller_id, sample_grant)
        
        assert status['current_usage'] == 150
        assert status['remaining_calls'] == 0
        assert status['rate_limit_exceeded'] is True
    
    @pytest.mark.asyncio
    async def test_per_caller_per_key_isolation(self, policy_engine):
        """Test that rate limits are isolated per caller per key"""
        key1 = "key-123"
        key2 = "key-456"
        caller1 = "caller-789"
        caller2 = "caller-abc"
        
        # Create grants for different combinations
        grant1 = AccessGrant.create_new(
            key_id=key1, caller_id=caller1,
            permissions={"max_calls_per_day": 10},
            expires_at=datetime.utcnow() + timedelta(hours=24),
            granted_by="owner"
        )
        
        grant2 = AccessGrant.create_new(
            key_id=key2, caller_id=caller1,
            permissions={"max_calls_per_day": 20},
            expires_at=datetime.utcnow() + timedelta(hours=24),
            granted_by="owner"
        )
        
        grant3 = AccessGrant.create_new(
            key_id=key1, caller_id=caller2,
            permissions={"max_calls_per_day": 15},
            expires_at=datetime.utcnow() + timedelta(hours=24),
            granted_by="owner"
        )
        
        # Use different amounts for each combination
        for _ in range(5):
            await policy_engine.increment_usage(key1, caller1)  # 5/10
        
        for _ in range(8):
            await policy_engine.increment_usage(key2, caller1)  # 8/20
        
        for _ in range(12):
            await policy_engine.increment_usage(key1, caller2)  # 12/15
        
        # Check rate limits are independent
        assert await policy_engine.check_rate_limit(key1, caller1, grant1) is True  # 5 < 10
        assert await policy_engine.check_rate_limit(key2, caller1, grant2) is True  # 8 < 20
        assert await policy_engine.check_rate_limit(key1, caller2, grant3) is True  # 12 < 15
        
        # Verify usage counts are correct
        assert await policy_engine.get_current_usage(key1, caller1) == 5
        assert await policy_engine.get_current_usage(key2, caller1) == 8
        assert await policy_engine.get_current_usage(key1, caller2) == 12
        assert await policy_engine.get_current_usage(key2, caller2) == 0  # No usage
    
    @pytest.mark.asyncio
    async def test_update_policy_placeholder(self, policy_engine):
        """Test policy update placeholder functionality"""
        # For MVP, this is just a placeholder
        result = await policy_engine.update_policy("key-123", {"max_calls": 200}, "owner-456")
        assert result is True
    
    @pytest.mark.asyncio
    async def test_increment_usage_invalid_params(self, policy_engine):
        """Test increment usage with invalid parameters"""
        # Should handle gracefully without errors
        await policy_engine.increment_usage("", "caller")  # Empty key_id
        await policy_engine.increment_usage("key", "")     # Empty caller_id
        await policy_engine.increment_usage("", "")        # Both empty
        
        # Verify no usage was recorded
        usage = await policy_engine.get_current_usage("key", "caller")
        assert usage == 0


if __name__ == "__main__":
    pytest.main([__file__])