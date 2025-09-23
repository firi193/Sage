#!/usr/bin/env python3
"""
Simple validation script for core data models
"""

import sys
from datetime import datetime, date, timedelta

# Add current directory to path
sys.path.append('.')

from sage.models import StoredKey, AccessGrant, PrivacyAuditLog, UsageCounter

def test_stored_key():
    """Test StoredKey model"""
    print("Testing StoredKey...")
    
    # Create new key
    key = StoredKey.create_new(
        owner_id="owner123",
        key_name="OpenAI API Key",
        encrypted_key=b"encrypted_data",
        coral_session_id="session123"
    )
    
    # Validate
    assert key.validate(), "StoredKey validation failed"
    
    # Test serialization
    data = key.to_dict()
    restored_key = StoredKey.from_dict(data)
    assert restored_key.key_id == key.key_id, "Serialization failed"
    
    print("✓ StoredKey tests passed")

def test_access_grant():
    """Test AccessGrant model"""
    print("Testing AccessGrant...")
    
    # Create new grant
    expires_at = datetime.utcnow() + timedelta(days=30)
    grant = AccessGrant.create_new(
        key_id="key123",
        caller_id="caller123",
        permissions={"max_calls_per_day": 100},
        expires_at=expires_at,
        granted_by="owner123"
    )
    
    # Validate
    assert grant.validate(), "AccessGrant validation failed"
    assert not grant.is_expired(), "Grant should not be expired"
    assert grant.is_valid(), "Grant should be valid"
    
    # Test serialization
    data = grant.to_dict()
    restored_grant = AccessGrant.from_dict(data)
    assert restored_grant.grant_id == grant.grant_id, "Serialization failed"
    
    print("✓ AccessGrant tests passed")

def test_privacy_audit_log():
    """Test PrivacyAuditLog model"""
    print("Testing PrivacyAuditLog...")
    
    # Create new log
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
    
    # Validate
    assert log.validate(), "PrivacyAuditLog validation failed"
    assert not log.is_error(), "Log should not be an error"
    
    # Test serialization
    data = log.to_dict()
    restored_log = PrivacyAuditLog.from_dict(data)
    assert restored_log.log_id == log.log_id, "Serialization failed"
    
    print("✓ PrivacyAuditLog tests passed")

def test_usage_counter():
    """Test UsageCounter model"""
    print("Testing UsageCounter...")
    
    # Create new counter
    counter = UsageCounter.create_new(
        key_id="key123",
        caller_id="caller123"
    )
    
    # Validate
    assert counter.validate(), "UsageCounter validation failed"
    assert counter.call_count == 0, "Initial call count should be 0"
    
    # Test increment
    counter.increment_usage(payload_size=100, response_time=200.0)
    assert counter.call_count == 1, "Call count should be 1"
    assert counter.total_payload_size == 100, "Payload size should be 100"
    assert counter.average_response_time == 200.0, "Response time should be 200.0"
    
    # Test serialization
    data = counter.to_dict()
    restored_counter = UsageCounter.from_dict(data)
    assert restored_counter.key_id == counter.key_id, "Serialization failed"
    
    print("✓ UsageCounter tests passed")

def main():
    """Run all model tests"""
    print("Validating Sage core data models...")
    print("=" * 40)
    
    try:
        test_stored_key()
        test_access_grant()
        test_privacy_audit_log()
        test_usage_counter()
        
        print("=" * 40)
        print("✅ All model tests passed successfully!")
        print("\nCore data models are working correctly:")
        print("- StoredKey: Encrypted API key storage")
        print("- AccessGrant: Permission management")
        print("- PrivacyAuditLog: Privacy-conscious logging")
        print("- UsageCounter: Usage tracking and rate limiting")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()