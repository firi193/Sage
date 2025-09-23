"""
Unit tests for KeyManager service
"""

import pytest
import asyncio
import tempfile
import os
from datetime import datetime
from unittest.mock import Mock, patch, AsyncMock

from sage.services.key_manager import KeyManager
from sage.services.key_storage import KeyStorageService
from sage.utils.encryption import EncryptionManager
from sage.models.stored_key import StoredKey


class TestKeyManager:
    """Test cases for KeyManager class"""
    
    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing"""
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        yield path
        if os.path.exists(path):
            os.unlink(path)
    
    @pytest.fixture
    def encryption_manager(self):
        """Create encryption manager for testing"""
        return EncryptionManager()
    
    @pytest.fixture
    def storage_service(self, temp_db, encryption_manager):
        """Create storage service for testing"""
        return KeyStorageService(db_path=temp_db, encryption_manager=encryption_manager)
    
    @pytest.fixture
    def key_manager(self, storage_service, encryption_manager):
        """Create KeyManager instance for testing"""
        return KeyManager(storage_service=storage_service, encryption_manager=encryption_manager)
    
    @pytest.mark.asyncio
    async def test_store_key_success(self, key_manager):
        """Test successful key storage"""
        key_name = "test-openai-key"
        api_key = "sk-test123456789abcdef"
        owner_id = "coral-user-123"
        coral_session_id = "session-456"
        
        key_id = await key_manager.store_key(key_name, api_key, owner_id, coral_session_id)
        
        assert key_id is not None
        assert isinstance(key_id, str)
        assert len(key_id) > 0
    
    @pytest.mark.asyncio
    async def test_store_key_invalid_api_key(self, key_manager):
        """Test storing invalid API key"""
        key_name = "test-key"
        invalid_api_key = ""  # Empty key
        owner_id = "coral-user-123"
        coral_session_id = "session-456"
        
        with pytest.raises(ValueError, match="Invalid API key format"):
            await key_manager.store_key(key_name, invalid_api_key, owner_id, coral_session_id)
    
    @pytest.mark.asyncio
    async def test_store_key_empty_key_name(self, key_manager):
        """Test storing key with empty name"""
        key_name = ""
        api_key = "sk-test123456789abcdef"
        owner_id = "coral-user-123"
        coral_session_id = "session-456"
        
        with pytest.raises(ValueError, match="Key name cannot be empty"):
            await key_manager.store_key(key_name, api_key, owner_id, coral_session_id)
    
    @pytest.mark.asyncio
    async def test_store_key_empty_owner_id(self, key_manager):
        """Test storing key with empty owner ID"""
        key_name = "test-key"
        api_key = "sk-test123456789abcdef"
        owner_id = ""
        coral_session_id = "session-456"
        
        with pytest.raises(ValueError, match="Owner ID cannot be empty"):
            await key_manager.store_key(key_name, api_key, owner_id, coral_session_id)
    
    @pytest.mark.asyncio
    async def test_store_key_duplicate_name(self, key_manager):
        """Test storing key with duplicate name for same owner"""
        key_name = "duplicate-key"
        api_key = "sk-test123456789abcdef"
        owner_id = "coral-user-123"
        coral_session_id = "session-456"
        
        # Store first key
        await key_manager.store_key(key_name, api_key, owner_id, coral_session_id)
        
        # Try to store duplicate
        with pytest.raises(ValueError, match="Key name 'duplicate-key' already exists"):
            await key_manager.store_key(key_name, api_key, owner_id, coral_session_id)
    
    @pytest.mark.asyncio
    async def test_retrieve_key_for_proxy_success(self, key_manager):
        """Test successful key retrieval for proxy"""
        key_name = "test-key"
        api_key = "sk-test123456789abcdef"
        owner_id = "coral-user-123"
        coral_session_id = "session-456"
        
        # Store key first
        key_id = await key_manager.store_key(key_name, api_key, owner_id, coral_session_id)
        
        # Retrieve key
        retrieved_key = await key_manager._retrieve_key_for_proxy(key_id)
        
        assert retrieved_key == api_key
    
    @pytest.mark.asyncio
    async def test_retrieve_key_for_proxy_not_found(self, key_manager):
        """Test retrieving non-existent key"""
        non_existent_key_id = "non-existent-key-id"
        
        with pytest.raises(ValueError, match="Key not found"):
            await key_manager._retrieve_key_for_proxy(non_existent_key_id)
    
    @pytest.mark.asyncio
    async def test_retrieve_key_for_proxy_inactive(self, key_manager):
        """Test retrieving inactive key"""
        key_name = "test-key"
        api_key = "sk-test123456789abcdef"
        owner_id = "coral-user-123"
        coral_session_id = "session-456"
        
        # Store and then revoke key
        key_id = await key_manager.store_key(key_name, api_key, owner_id, coral_session_id)
        await key_manager.revoke_key(key_id, owner_id)
        
        with pytest.raises(ValueError, match="Key is inactive"):
            await key_manager._retrieve_key_for_proxy(key_id)
    
    @pytest.mark.asyncio
    async def test_list_keys_success(self, key_manager):
        """Test successful key listing"""
        owner_id = "coral-user-123"
        coral_session_id = "session-456"
        
        # Store multiple keys
        key1_id = await key_manager.store_key("key1", "sk-test1", owner_id, coral_session_id)
        key2_id = await key_manager.store_key("key2", "sk-test2", owner_id, coral_session_id)
        
        # List keys
        keys = await key_manager.list_keys(owner_id)
        
        assert len(keys) == 2
        assert all('key_id' in key for key in keys)
        assert all('key_name' in key for key in keys)
        assert all('created_at' in key for key in keys)
        assert all('is_active' in key for key in keys)
        
        # Verify no actual key values are exposed
        assert all('encrypted_key' not in key for key in keys)
        assert all('api_key' not in key for key in keys)
    
    @pytest.mark.asyncio
    async def test_list_keys_empty_owner_id(self, key_manager):
        """Test listing keys with empty owner ID"""
        with pytest.raises(ValueError, match="Owner ID cannot be empty"):
            await key_manager.list_keys("")
    
    @pytest.mark.asyncio
    async def test_rotate_key_success(self, key_manager):
        """Test successful key rotation"""
        key_name = "test-key"
        original_api_key = "sk-original123"
        new_api_key = "sk-rotated456"
        owner_id = "coral-user-123"
        coral_session_id = "session-456"
        
        # Store original key
        key_id = await key_manager.store_key(key_name, original_api_key, owner_id, coral_session_id)
        
        # Rotate key
        success = await key_manager.rotate_key(key_id, new_api_key, owner_id)
        assert success is True
        
        # Verify new key is retrievable
        retrieved_key = await key_manager._retrieve_key_for_proxy(key_id)
        assert retrieved_key == new_api_key
    
    @pytest.mark.asyncio
    async def test_rotate_key_invalid_new_key(self, key_manager):
        """Test rotating with invalid new key"""
        key_name = "test-key"
        api_key = "sk-test123456789abcdef"
        owner_id = "coral-user-123"
        coral_session_id = "session-456"
        
        # Store key first
        key_id = await key_manager.store_key(key_name, api_key, owner_id, coral_session_id)
        
        # Try to rotate with invalid key
        with pytest.raises(ValueError, match="Invalid new API key format"):
            await key_manager.rotate_key(key_id, "", owner_id)
    
    @pytest.mark.asyncio
    async def test_rotate_key_not_found(self, key_manager):
        """Test rotating non-existent key"""
        non_existent_key_id = "non-existent-key-id"
        new_api_key = "sk-new123"
        owner_id = "coral-user-123"
        
        with pytest.raises(ValueError, match="Key not found or access denied"):
            await key_manager.rotate_key(non_existent_key_id, new_api_key, owner_id)
    
    @pytest.mark.asyncio
    async def test_rotate_key_wrong_owner(self, key_manager):
        """Test rotating key with wrong owner"""
        key_name = "test-key"
        api_key = "sk-test123456789abcdef"
        owner_id = "coral-user-123"
        wrong_owner_id = "coral-user-456"
        coral_session_id = "session-456"
        
        # Store key with one owner
        key_id = await key_manager.store_key(key_name, api_key, owner_id, coral_session_id)
        
        # Try to rotate with different owner
        with pytest.raises(ValueError, match="Key not found or access denied"):
            await key_manager.rotate_key(key_id, "sk-new123", wrong_owner_id)
    
    @pytest.mark.asyncio
    async def test_revoke_key_success(self, key_manager):
        """Test successful key revocation"""
        key_name = "test-key"
        api_key = "sk-test123456789abcdef"
        owner_id = "coral-user-123"
        coral_session_id = "session-456"
        
        # Store key first
        key_id = await key_manager.store_key(key_name, api_key, owner_id, coral_session_id)
        
        # Revoke key
        success = await key_manager.revoke_key(key_id, owner_id)
        assert success is True
        
        # Verify key is no longer retrievable
        with pytest.raises(ValueError, match="Key is inactive"):
            await key_manager._retrieve_key_for_proxy(key_id)
    
    @pytest.mark.asyncio
    async def test_revoke_key_not_found(self, key_manager):
        """Test revoking non-existent key"""
        non_existent_key_id = "non-existent-key-id"
        owner_id = "coral-user-123"
        
        with pytest.raises(ValueError, match="Key not found or access denied"):
            await key_manager.revoke_key(non_existent_key_id, owner_id)
    
    @pytest.mark.asyncio
    async def test_revoke_key_wrong_owner(self, key_manager):
        """Test revoking key with wrong owner"""
        key_name = "test-key"
        api_key = "sk-test123456789abcdef"
        owner_id = "coral-user-123"
        wrong_owner_id = "coral-user-456"
        coral_session_id = "session-456"
        
        # Store key with one owner
        key_id = await key_manager.store_key(key_name, api_key, owner_id, coral_session_id)
        
        # Try to revoke with different owner
        with pytest.raises(ValueError, match="Key not found or access denied"):
            await key_manager.revoke_key(key_id, wrong_owner_id)
    
    @pytest.mark.asyncio
    async def test_verify_key_ownership_success(self, key_manager):
        """Test successful key ownership verification"""
        key_name = "test-key"
        api_key = "sk-test123456789abcdef"
        owner_id = "coral-user-123"
        coral_session_id = "session-456"
        
        # Store key first
        key_id = await key_manager.store_key(key_name, api_key, owner_id, coral_session_id)
        
        # Verify ownership
        is_owner = await key_manager.verify_key_ownership(key_id, owner_id)
        assert is_owner is True
    
    @pytest.mark.asyncio
    async def test_verify_key_ownership_wrong_owner(self, key_manager):
        """Test key ownership verification with wrong owner"""
        key_name = "test-key"
        api_key = "sk-test123456789abcdef"
        owner_id = "coral-user-123"
        wrong_owner_id = "coral-user-456"
        coral_session_id = "session-456"
        
        # Store key with one owner
        key_id = await key_manager.store_key(key_name, api_key, owner_id, coral_session_id)
        
        # Verify with wrong owner
        is_owner = await key_manager.verify_key_ownership(key_id, wrong_owner_id)
        assert is_owner is False
    
    @pytest.mark.asyncio
    async def test_verify_key_ownership_empty_owner(self, key_manager):
        """Test key ownership verification with empty owner ID"""
        is_owner = await key_manager.verify_key_ownership("some-key-id", "")
        assert is_owner is False
    
    @pytest.mark.asyncio
    async def test_get_key_metadata_success(self, key_manager):
        """Test successful key metadata retrieval"""
        key_name = "test-key"
        api_key = "sk-test123456789abcdef"
        owner_id = "coral-user-123"
        coral_session_id = "session-456"
        
        # Store key first
        key_id = await key_manager.store_key(key_name, api_key, owner_id, coral_session_id)
        
        # Get metadata
        metadata = await key_manager.get_key_metadata(key_id, owner_id)
        
        assert metadata is not None
        assert metadata['key_id'] == key_id
        assert metadata['key_name'] == key_name
        assert metadata['owner_id'] == owner_id
        assert metadata['is_active'] is True
        assert 'created_at' in metadata
        assert 'last_rotated' in metadata
        
        # Verify no actual key value is exposed
        assert 'encrypted_key' not in metadata
        assert 'api_key' not in metadata
    
    @pytest.mark.asyncio
    async def test_get_key_metadata_wrong_owner(self, key_manager):
        """Test key metadata retrieval with wrong owner"""
        key_name = "test-key"
        api_key = "sk-test123456789abcdef"
        owner_id = "coral-user-123"
        wrong_owner_id = "coral-user-456"
        coral_session_id = "session-456"
        
        # Store key with one owner
        key_id = await key_manager.store_key(key_name, api_key, owner_id, coral_session_id)
        
        # Try to get metadata with wrong owner
        metadata = await key_manager.get_key_metadata(key_id, wrong_owner_id)
        assert metadata is None
    
    @pytest.mark.asyncio
    async def test_get_key_metadata_empty_owner(self, key_manager):
        """Test key metadata retrieval with empty owner ID"""
        metadata = await key_manager.get_key_metadata("some-key-id", "")
        assert metadata is None


class TestKeyManagerIntegration:
    """Integration tests for KeyManager with real storage"""
    
    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing"""
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        yield path
        if os.path.exists(path):
            os.unlink(path)
    
    @pytest.fixture
    def key_manager(self, temp_db):
        """Create KeyManager with real storage for integration testing"""
        encryption_manager = EncryptionManager()
        storage_service = KeyStorageService(db_path=temp_db, encryption_manager=encryption_manager)
        return KeyManager(storage_service=storage_service, encryption_manager=encryption_manager)
    
    @pytest.mark.asyncio
    async def test_full_key_lifecycle(self, key_manager):
        """Test complete key lifecycle: store -> list -> rotate -> revoke"""
        key_name = "lifecycle-test-key"
        original_api_key = "sk-original123456"
        rotated_api_key = "sk-rotated789012"
        owner_id = "coral-user-lifecycle"
        coral_session_id = "session-lifecycle"
        
        # 1. Store key
        key_id = await key_manager.store_key(key_name, original_api_key, owner_id, coral_session_id)
        assert key_id is not None
        
        # 2. List keys
        keys = await key_manager.list_keys(owner_id)
        assert len(keys) == 1
        assert keys[0]['key_id'] == key_id
        assert keys[0]['key_name'] == key_name
        
        # 3. Retrieve key for proxy
        retrieved_key = await key_manager._retrieve_key_for_proxy(key_id)
        assert retrieved_key == original_api_key
        
        # 4. Rotate key
        success = await key_manager.rotate_key(key_id, rotated_api_key, owner_id)
        assert success is True
        
        # 5. Verify rotated key
        retrieved_key = await key_manager._retrieve_key_for_proxy(key_id)
        assert retrieved_key == rotated_api_key
        
        # 6. Revoke key
        success = await key_manager.revoke_key(key_id, owner_id)
        assert success is True
        
        # 7. Verify key is inactive
        with pytest.raises(ValueError, match="Key is inactive"):
            await key_manager._retrieve_key_for_proxy(key_id)
        
        # 8. Verify key no longer appears in active list
        keys = await key_manager.list_keys(owner_id)
        assert len(keys) == 0
    
    @pytest.mark.asyncio
    async def test_multiple_owners_isolation(self, key_manager):
        """Test that keys are properly isolated between owners"""
        key_name = "shared-name"
        api_key1 = "sk-owner1-key"
        api_key2 = "sk-owner2-key"
        owner1_id = "coral-user-1"
        owner2_id = "coral-user-2"
        coral_session_id = "session-test"
        
        # Store keys for different owners with same name
        key1_id = await key_manager.store_key(key_name, api_key1, owner1_id, coral_session_id)
        key2_id = await key_manager.store_key(key_name, api_key2, owner2_id, coral_session_id)
        
        # Verify each owner only sees their own keys
        owner1_keys = await key_manager.list_keys(owner1_id)
        owner2_keys = await key_manager.list_keys(owner2_id)
        
        assert len(owner1_keys) == 1
        assert len(owner2_keys) == 1
        assert owner1_keys[0]['key_id'] == key1_id
        assert owner2_keys[0]['key_id'] == key2_id
        
        # Verify ownership isolation
        assert await key_manager.verify_key_ownership(key1_id, owner1_id) is True
        assert await key_manager.verify_key_ownership(key1_id, owner2_id) is False
        assert await key_manager.verify_key_ownership(key2_id, owner1_id) is False
        assert await key_manager.verify_key_ownership(key2_id, owner2_id) is True