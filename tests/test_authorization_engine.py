"""
Unit tests for AuthorizationEngine
"""

import pytest
import asyncio
import os
import tempfile
from datetime import datetime, timedelta
from unittest.mock import patch

from sage.services.authorization_engine import AuthorizationEngine
from sage.models.access_grant import AccessGrant


class TestAuthorizationEngine:
    """Test suite for AuthorizationEngine"""
    
    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing"""
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        yield path
        # Cleanup
        if os.path.exists(path):
            os.unlink(path)
    
    @pytest.fixture
    def auth_engine(self, temp_db):
        """Create AuthorizationEngine instance with temporary database"""
        return AuthorizationEngine(db_path=temp_db)
    
    @pytest.fixture
    def sample_permissions(self):
        """Sample permissions for testing"""
        return {"max_calls_per_day": 100}
    
    @pytest.fixture
    def future_expiry(self):
        """Future expiry time for testing"""
        return datetime.utcnow() + timedelta(days=1)
    
    @pytest.mark.asyncio
    async def test_create_grant_success(self, auth_engine, sample_permissions, future_expiry):
        """Test successful grant creation"""
        key_id = "test-key-123"
        caller_id = "caller-session-456"
        owner_id = "owner-session-789"
        
        grant_id = await auth_engine.create_grant(
            key_id=key_id,
            caller_id=caller_id,
            permissions=sample_permissions,
            expires_at=future_expiry,
            owner_id=owner_id
        )
        
        assert grant_id is not None
        assert isinstance(grant_id, str)
        assert len(grant_id) > 0
    
    @pytest.mark.asyncio
    async def test_create_grant_invalid_inputs(self, auth_engine, sample_permissions, future_expiry):
        """Test grant creation with invalid inputs"""
        # Empty key_id
        with pytest.raises(ValueError, match="Key ID cannot be empty"):
            await auth_engine.create_grant("", "caller", sample_permissions, future_expiry, "owner")
        
        # Empty caller_id
        with pytest.raises(ValueError, match="Caller ID cannot be empty"):
            await auth_engine.create_grant("key", "", sample_permissions, future_expiry, "owner")
        
        # Empty owner_id
        with pytest.raises(ValueError, match="Owner ID cannot be empty"):
            await auth_engine.create_grant("key", "caller", sample_permissions, future_expiry, "")
        
        # Invalid permissions type
        with pytest.raises(ValueError, match="Permissions must be a dictionary"):
            await auth_engine.create_grant("key", "caller", "invalid", future_expiry, "owner")
        
        # Past expiry time
        past_time = datetime.utcnow() - timedelta(hours=1)
        with pytest.raises(ValueError, match="Expiry time must be in the future"):
            await auth_engine.create_grant("key", "caller", sample_permissions, past_time, "owner")
        
        # Missing max_calls_per_day
        invalid_permissions = {"other_setting": 50}
        with pytest.raises(ValueError, match="Permissions must include max_calls_per_day"):
            await auth_engine.create_grant("key", "caller", invalid_permissions, future_expiry, "owner")
        
        # Invalid max_calls_per_day
        invalid_permissions = {"max_calls_per_day": -1}
        with pytest.raises(ValueError, match="max_calls_per_day must be a positive integer"):
            await auth_engine.create_grant("key", "caller", invalid_permissions, future_expiry, "owner")
    
    @pytest.mark.asyncio
    async def test_check_authorization_success(self, auth_engine, sample_permissions, future_expiry):
        """Test successful authorization check"""
        key_id = "test-key-123"
        caller_id = "caller-session-456"
        owner_id = "owner-session-789"
        
        # Create grant first
        await auth_engine.create_grant(
            key_id=key_id,
            caller_id=caller_id,
            permissions=sample_permissions,
            expires_at=future_expiry,
            owner_id=owner_id
        )
        
        # Check authorization
        is_authorized = await auth_engine.check_authorization(key_id, caller_id)
        assert is_authorized is True
    
    @pytest.mark.asyncio
    async def test_check_authorization_no_grant(self, auth_engine):
        """Test authorization check with no existing grant"""
        is_authorized = await auth_engine.check_authorization("nonexistent-key", "caller")
        assert is_authorized is False
    
    @pytest.mark.asyncio
    async def test_check_authorization_expired_grant(self, auth_engine, sample_permissions):
        """Test authorization check with expired grant"""
        key_id = "test-key-123"
        caller_id = "caller-session-456"
        owner_id = "owner-session-789"
        
        # Create grant that expires in the past
        past_expiry = datetime.utcnow() - timedelta(hours=1)
        await auth_engine.create_grant(
            key_id=key_id,
            caller_id=caller_id,
            permissions=sample_permissions,
            expires_at=past_expiry,
            owner_id=owner_id,
            _allow_past_expiry=True
        )
        
        # Check authorization - should be False due to expiry
        is_authorized = await auth_engine.check_authorization(key_id, caller_id)
        assert is_authorized is False
    
    @pytest.mark.asyncio
    async def test_get_grant_success(self, auth_engine, sample_permissions, future_expiry):
        """Test successful grant retrieval"""
        key_id = "test-key-123"
        caller_id = "caller-session-456"
        owner_id = "owner-session-789"
        
        # Create grant first
        grant_id = await auth_engine.create_grant(
            key_id=key_id,
            caller_id=caller_id,
            permissions=sample_permissions,
            expires_at=future_expiry,
            owner_id=owner_id
        )
        
        # Retrieve grant
        grant = await auth_engine.get_grant(key_id, caller_id)
        assert grant is not None
        assert grant.grant_id == grant_id
        assert grant.key_id == key_id
        assert grant.caller_id == caller_id
        assert grant.permissions == sample_permissions
        assert grant.granted_by == owner_id
        assert grant.is_active is True
        assert not grant.is_expired()
    
    @pytest.mark.asyncio
    async def test_get_grant_not_found(self, auth_engine):
        """Test grant retrieval when grant doesn't exist"""
        grant = await auth_engine.get_grant("nonexistent-key", "caller")
        assert grant is None
    
    @pytest.mark.asyncio
    async def test_get_grant_expired(self, auth_engine, sample_permissions):
        """Test grant retrieval when grant is expired"""
        key_id = "test-key-123"
        caller_id = "caller-session-456"
        owner_id = "owner-session-789"
        
        # Create expired grant
        past_expiry = datetime.utcnow() - timedelta(hours=1)
        await auth_engine.create_grant(
            key_id=key_id,
            caller_id=caller_id,
            permissions=sample_permissions,
            expires_at=past_expiry,
            owner_id=owner_id,
            _allow_past_expiry=True
        )
        
        # Try to retrieve - should return None and deactivate grant
        grant = await auth_engine.get_grant(key_id, caller_id)
        assert grant is None
    
    @pytest.mark.asyncio
    async def test_revoke_grant_success(self, auth_engine, sample_permissions, future_expiry):
        """Test successful grant revocation"""
        key_id = "test-key-123"
        caller_id = "caller-session-456"
        owner_id = "owner-session-789"
        
        # Create grant first
        grant_id = await auth_engine.create_grant(
            key_id=key_id,
            caller_id=caller_id,
            permissions=sample_permissions,
            expires_at=future_expiry,
            owner_id=owner_id
        )
        
        # Revoke grant
        success = await auth_engine.revoke_grant(grant_id, owner_id)
        assert success is True
        
        # Verify grant is no longer active
        is_authorized = await auth_engine.check_authorization(key_id, caller_id)
        assert is_authorized is False
    
    @pytest.mark.asyncio
    async def test_revoke_grant_not_found(self, auth_engine):
        """Test grant revocation when grant doesn't exist"""
        with pytest.raises(ValueError, match="Grant not found or already inactive"):
            await auth_engine.revoke_grant("nonexistent-grant", "owner")
    
    @pytest.mark.asyncio
    async def test_revoke_grant_wrong_owner(self, auth_engine, sample_permissions, future_expiry):
        """Test grant revocation by wrong owner"""
        key_id = "test-key-123"
        caller_id = "caller-session-456"
        owner_id = "owner-session-789"
        wrong_owner = "wrong-owner-999"
        
        # Create grant first
        grant_id = await auth_engine.create_grant(
            key_id=key_id,
            caller_id=caller_id,
            permissions=sample_permissions,
            expires_at=future_expiry,
            owner_id=owner_id
        )
        
        # Try to revoke with wrong owner
        with pytest.raises(ValueError, match="Access denied: grant not owned by requester"):
            await auth_engine.revoke_grant(grant_id, wrong_owner)
    
    @pytest.mark.asyncio
    async def test_revoke_grants_for_key(self, auth_engine, sample_permissions, future_expiry):
        """Test revoking all grants for a specific key"""
        key_id = "test-key-123"
        owner_id = "owner-session-789"
        
        # Create multiple grants for the same key
        caller1 = "caller1"
        caller2 = "caller2"
        
        await auth_engine.create_grant(key_id, caller1, sample_permissions, future_expiry, owner_id)
        await auth_engine.create_grant(key_id, caller2, sample_permissions, future_expiry, owner_id)
        
        # Revoke all grants for the key
        revoked_count = await auth_engine.revoke_grants_for_key(key_id, owner_id)
        assert revoked_count == 2
        
        # Verify both grants are no longer active
        assert await auth_engine.check_authorization(key_id, caller1) is False
        assert await auth_engine.check_authorization(key_id, caller2) is False
    
    @pytest.mark.asyncio
    async def test_cleanup_expired_grants(self, auth_engine, sample_permissions):
        """Test cleanup of expired grants"""
        key_id = "test-key-123"
        caller_id = "caller-session-456"
        owner_id = "owner-session-789"
        
        # Create expired grant
        past_expiry = datetime.utcnow() - timedelta(hours=1)
        await auth_engine.create_grant(
            key_id=key_id,
            caller_id=caller_id,
            permissions=sample_permissions,
            expires_at=past_expiry,
            owner_id=owner_id,
            _allow_past_expiry=True
        )
        
        # Create active grant
        future_expiry = datetime.utcnow() + timedelta(days=1)
        await auth_engine.create_grant(
            key_id="active-key",
            caller_id="active-caller",
            permissions=sample_permissions,
            expires_at=future_expiry,
            owner_id=owner_id
        )
        
        # Cleanup expired grants
        cleaned_count = await auth_engine.cleanup_expired_grants()
        assert cleaned_count == 1
        
        # Verify expired grant is no longer active
        assert await auth_engine.check_authorization(key_id, caller_id) is False
        # Verify active grant is still active
        assert await auth_engine.check_authorization("active-key", "active-caller") is True
    
    @pytest.mark.asyncio
    async def test_list_grants_by_owner(self, auth_engine, sample_permissions, future_expiry):
        """Test listing grants by owner"""
        owner_id = "owner-session-789"
        key_id1 = "key1"
        key_id2 = "key2"
        caller1 = "caller1"
        caller2 = "caller2"
        
        # Create grants
        grant_id1 = await auth_engine.create_grant(key_id1, caller1, sample_permissions, future_expiry, owner_id)
        grant_id2 = await auth_engine.create_grant(key_id2, caller2, sample_permissions, future_expiry, owner_id)
        
        # List grants
        grants = await auth_engine.list_grants_by_owner(owner_id)
        assert len(grants) == 2
        
        grant_ids = [g['grant_id'] for g in grants]
        assert grant_id1 in grant_ids
        assert grant_id2 in grant_ids
        
        # Verify grant structure
        for grant in grants:
            assert 'grant_id' in grant
            assert 'key_id' in grant
            assert 'caller_id' in grant
            assert 'permissions' in grant
            assert 'created_at' in grant
            assert 'expires_at' in grant
            assert 'is_active' in grant
            assert 'is_expired' in grant
            assert grant['is_active'] is True
            assert grant['is_expired'] is False
    
    @pytest.mark.asyncio
    async def test_list_grants_by_owner_empty(self, auth_engine):
        """Test listing grants for owner with no grants"""
        grants = await auth_engine.list_grants_by_owner("nonexistent-owner")
        assert grants == []
    
    @pytest.mark.asyncio
    async def test_validate_coral_identity_success(self, auth_engine):
        """Test successful Coral identity validation"""
        session_id = "valid-session-12345678"
        caller_id = await auth_engine.validate_coral_identity(session_id)
        assert caller_id == session_id
    
    @pytest.mark.asyncio
    async def test_validate_coral_identity_invalid(self, auth_engine):
        """Test Coral identity validation with invalid inputs"""
        # Empty session ID
        with pytest.raises(ValueError, match="Session ID cannot be empty"):
            await auth_engine.validate_coral_identity("")
        
        # Short session ID
        with pytest.raises(ValueError, match="Invalid session ID format"):
            await auth_engine.validate_coral_identity("short")
    
    @pytest.mark.asyncio
    async def test_grant_replacement(self, auth_engine, sample_permissions, future_expiry):
        """Test that creating a new grant for same key/caller replaces the old one"""
        key_id = "test-key-123"
        caller_id = "caller-session-456"
        owner_id = "owner-session-789"
        
        # Create first grant
        grant_id1 = await auth_engine.create_grant(
            key_id=key_id,
            caller_id=caller_id,
            permissions=sample_permissions,
            expires_at=future_expiry,
            owner_id=owner_id
        )
        
        # Create second grant for same key/caller with different permissions
        new_permissions = {"max_calls_per_day": 200}
        grant_id2 = await auth_engine.create_grant(
            key_id=key_id,
            caller_id=caller_id,
            permissions=new_permissions,
            expires_at=future_expiry,
            owner_id=owner_id
        )
        
        # Should be different grant IDs
        assert grant_id1 != grant_id2
        
        # Should still be authorized
        assert await auth_engine.check_authorization(key_id, caller_id) is True
        
        # Should have new permissions
        grant = await auth_engine.get_grant(key_id, caller_id)
        assert grant is not None
        assert grant.permissions == new_permissions
        assert grant.grant_id == grant_id2
    
    @pytest.mark.asyncio
    async def test_database_initialization(self, temp_db):
        """Test that database is properly initialized"""
        # Create engine - should initialize database
        auth_engine = AuthorizationEngine(db_path=temp_db)
        
        # Verify database file exists
        assert os.path.exists(temp_db)
        
        # Verify we can perform operations
        future_expiry = datetime.utcnow() + timedelta(days=1)
        permissions = {"max_calls_per_day": 100}
        
        grant_id = await auth_engine.create_grant(
            key_id="test-key",
            caller_id="test-caller",
            permissions=permissions,
            expires_at=future_expiry,
            owner_id="test-owner"
        )
        
        assert grant_id is not None


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])