"""
Tests for core data models
"""

import pytest
from datetime import datetime, date, timedelta
from sage.models import StoredKey, AccessGrant, PrivacyAuditLog, UsageCounter


class TestStoredKey:
    def test_create_new(self):
        """Test creating a new StoredKey"""
        key = StoredKey.create_new(
            owner_id="owner123",
            key_name="OpenAI API Key",
            encrypted_key=b"encrypted_data",
            coral_session_id="session123"
        )
        
        assert key.owner_id == "owner123"
        assert key.key_name == "OpenAI API Key"
        assert key.encrypted_key == b"encrypted_data"
        assert key.coral_session_id == "session123"
        assert key.is_active is True
        assert isinstance(key.key_id, str)
        assert isinstance(key.created_at, datetime)
        assert isinstance(key.last_rotated, datetime)

    def test_validation(self):
        """Test StoredKey validation"""
        key = StoredKey.create_new(
            owner_id="owner123",
            key_name="Test Key",
            encrypted_key=b"encrypted",
            coral_session_id="session123"
        )
        assert key.validate() is True
        
        # Test invalid key
        key.key_id = ""
        assert key.validate() is False

    def test_serialization(self):
        """Test to_dict and from_dict methods"""
        key = StoredKey.create_new(
            owner_id="owner123",
            key_name="Test Key",
            encrypted_key=b"encrypted",
            coral_session_id="session123"
        )
        
        data = key.to_dict()
        restored_key = StoredKey.from_dict(data)
        
        assert restored_key.key_id == key.key_id
        assert restored_key.owner_id == key.owner_id
        assert restored_key.encrypted_key == key.encrypted_key


class TestAccessGrant:
    def test_create_new(self):
        """Test creating a new AccessGrant"""
        expires_at = datetime.utcnow() + timedelta(days=30)
        grant = AccessGrant.create_new(
            key_id="key123",
            caller_id="caller123",
            permissions={"max_calls_per_day": 100},
            expires_at=expires_at,
            granted_by="owner123"
        )
        
        assert grant.key_id == "key123"
        assert grant.caller_id == "caller123"
        assert grant.permissions["max_calls_per_day"] == 100
        assert grant.expires_at == expires_at
        assert grant.granted_by == "owner123"
        assert grant.is_active is True
        assert isinstance(grant.grant_id, str)

    def test_validation(self):
        """Test AccessGrant validation"""
        expires_at = datetime.utcnow() + timedelta(days=30)
        grant = AccessGrant.create_new(
            key_id="key123",
            caller_id="caller123",
            permissions={"max_calls_per_day": 100},
            expires_at=expires_at,
            granted_by="owner123"
        )
        assert grant.validate() is True
        
        # Test invalid expiry (in the past)
        grant.expires_at = datetime.utcnow() - timedelta(days=1)
        assert grant.validate() is False

    def test_expiration(self):
        """Test grant expiration logic"""
        # Create expired grant
        expires_at = datetime.utcnow() - timedelta(days=1)
        grant = AccessGrant.create_new(
            key_id="key123",
            caller_id="caller123",
            permissions={"max_calls_per_day": 100},
            expires_at=expires_at,
            granted_by="owner123"
        )
        
        assert grant.is_expired() is True
        assert grant.is_valid() is False


class TestPrivacyAuditLog:
    def test_create_new(self):
        """Test creating a new PrivacyAuditLog"""
        log = PrivacyAuditLog.create_new(
            caller_id="caller123",
            key_id="key123",
            action="proxy_call",
            method="POST",
            endpoint="/api/chat",
            payload_size=1024,
            response_time=250.5,
            response_code=200
        )
        
        assert log.caller_id == "caller123"
        assert log.key_id == "key123"
        assert log.action == "proxy_call"
        assert log.method == "POST"
        assert log.endpoint == "/api/chat"
        assert log.payload_size == 1024
        assert log.response_time == 250.5
        assert log.response_code == 200
        assert isinstance(log.log_id, str)
        assert isinstance(log.timestamp, datetime)

    def test_validation(self):
        """Test PrivacyAuditLog validation"""
        log = PrivacyAuditLog.create_new(
            caller_id="caller123",
            key_id="key123",
            action="proxy_call",
            method="POST",
            endpoint="/api/chat",
            payload_size=1024,
            response_time=250.5,
            response_code=200
        )
        assert log.validate() is True
        
        # Test invalid payload size
        log.payload_size = -1
        assert log.validate() is False

    def test_error_detection(self):
        """Test error detection methods"""
        # Test error log
        error_log = PrivacyAuditLog.create_new(
            caller_id="caller123",
            key_id="key123",
            action="proxy_call",
            method="POST",
            endpoint="/api/chat",
            payload_size=1024,
            response_time=250.5,
            response_code=500,
            error_message="Internal server error"
        )
        
        assert error_log.is_error() is True
        
        # Test rate limit error
        rate_limit_log = PrivacyAuditLog.create_new(
            caller_id="caller123",
            key_id="key123",
            action="proxy_call",
            method="POST",
            endpoint="/api/chat",
            payload_size=1024,
            response_time=250.5,
            response_code=429
        )
        
        assert rate_limit_log.is_rate_limit_error() is True


class TestUsageCounter:
    def test_create_new(self):
        """Test creating a new UsageCounter"""
        counter = UsageCounter.create_new(
            key_id="key123",
            caller_id="caller123"
        )
        
        assert counter.key_id == "key123"
        assert counter.caller_id == "caller123"
        assert counter.call_count == 0
        assert counter.total_payload_size == 0
        assert counter.average_response_time == 0.0
        assert isinstance(counter.date, date)
        assert isinstance(counter.last_reset, datetime)

    def test_validation(self):
        """Test UsageCounter validation"""
        counter = UsageCounter.create_new(
            key_id="key123",
            caller_id="caller123"
        )
        assert counter.validate() is True
        
        # Test invalid call count
        counter.call_count = -1
        assert counter.validate() is False

    def test_increment_usage(self):
        """Test usage increment logic"""
        counter = UsageCounter.create_new(
            key_id="key123",
            caller_id="caller123"
        )
        
        # First call
        counter.increment_usage(payload_size=100, response_time=200.0)
        assert counter.call_count == 1
        assert counter.total_payload_size == 100
        assert counter.average_response_time == 200.0
        
        # Second call
        counter.increment_usage(payload_size=200, response_time=300.0)
        assert counter.call_count == 2
        assert counter.total_payload_size == 300
        assert counter.average_response_time == 250.0  # (200 + 300) / 2

    def test_reset_counter(self):
        """Test counter reset functionality"""
        counter = UsageCounter.create_new(
            key_id="key123",
            caller_id="caller123"
        )
        
        # Add some usage
        counter.increment_usage(payload_size=100, response_time=200.0)
        assert counter.call_count == 1
        
        # Reset
        counter.reset_daily_counter()
        assert counter.call_count == 0
        assert counter.total_payload_size == 0
        assert counter.average_response_time == 0.0