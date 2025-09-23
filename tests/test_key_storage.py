"""
Unit tests for key storage service
"""

import pytest
import os
import tempfile
from datetime import datetime, timedelta

from sage.models.stored_key import StoredKey
from sage.services.key_storage import KeyStorageService
from sage.utils.encryption import EncryptionManager


class TestKeyStorageService:
    """Test cases for KeyStorageService"""
    
    @pytest.fixture
    def temp_db_path(self):
        """Create temporary database file for testing"""
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        yield path
        # Cleanup
        if os.path.exists(path):
            os.unlink(path)
    
    @pytest.fixture
    def encryption_manager(self):
        """Create encryption manager for testing"""
        return EncryptionManager("test_key_for_storage")
    
    @pytest.fixture
    def storage_service(self, temp_db_path, encryption_manager):
        """Create key storage service for testing"""
        return KeyStorageService(temp_db_path, encryption_manager)
    
    @pytest.fixture
    def sample_stored_key(self, encryption_manager):
        """Create sample stored key for testing"""
        api_key = "sk-1234567890abcdef"
        encrypted_key = encryption_manager.encrypt(api_key)
        
        return StoredKey.create_new(
            owner_id="coral_user_123",
            key_name="OpenAI API Key",
            encrypted_key=encrypted_key,
            coral_session_id="session_456"
        )
    
    def test_init_creates_database(self, temp_db_path, encryption_manager):
        """Test that initialization creates database and tables"""
        assert not os.path.exists(temp_db_path)
        
        service = KeyStorageService(temp_db_path, encryption_manager)
        
        assert os.path.exists(temp_db_path)
        
        # Check that tables exist by getting stats
        stats = service.get_storage_stats()
        assert stats['database_exists'] is True
        assert stats['total_keys'] == 0
    
    def test_store_key_success(self, storage_service, sample_stored_key):
        """Test successful key storage"""
        result = storage_service.store_key(sample_stored_key)
        assert result is True
        
        # Verify it was stored
        retrieved = storage_service.get_key(sample_stored_key.key_id)
        assert retrieved is not None
        assert retrieved.key_id == sample_stored_key.key_id
        assert retrieved.owner_id == sample_stored_key.owner_id
        assert retrieved.key_name == sample_stored_key.key_name
        assert retrieved.encrypted_key == sample_stored_key.encrypted_key
    
    @pytest.mark.asyncio
    async def test_store_key_duplicate(self, storage_service, sample_stored_key):
        """Test storing duplicate key fails"""
        # Store first time
        result1 = await storage_service.store_key(sample_stored_key)
        assert result1 is True
        
        # Try to store same key again
        result2 = await storage_service.store_key(sample_stored_key)
        assert result2 is False
    
    @pytest.mark.asyncio
    async def test_store_key_invalid(self, storage_service):
        """Test storing invalid key fails"""
        # Create invalid stored key
        invalid_key = StoredKey(
            key_id="",  # Invalid empty key_id
            owner_id="owner",
            key_name="name",
            encrypted_key=b"encrypted",
            created_at=datetime.utcnow(),
            last_rotated=datetime.utcnow(),
            is_active=True,
            coral_session_id="session"
        )
        
        with pytest.raises(ValueError):
            await storage_service.store_key(invalid_key)
    
    @pytest.mark.asyncio
    async def test_get_key_exists(self, storage_service, sample_stored_key):
        """Test retrieving existing key"""
        # Store key first
        await storage_service.store_key(sample_stored_key)
        
        # Retrieve it
        retrieved = await storage_service.get_key(sample_stored_key.key_id)
        assert retrieved is not None
        assert retrieved.key_id == sample_stored_key.key_id
        assert retrieved.owner_id == sample_stored_key.owner_id
    
    @pytest.mark.asyncio
    async def test_get_key_not_exists(self, storage_service):
        """Test retrieving non-existent key"""
        retrieved = await storage_service.get_key("non_existent_key")
        assert retrieved is None
    
    @pytest.mark.asyncio
    async def test_get_keys_by_owner(self, storage_service, encryption_manager):
        """Test retrieving keys by owner"""
        owner_id = "coral_user_123"
        
        # Create multiple keys for same owner
        key1 = StoredKey.create_new(
            owner_id=owner_id,
            key_name="Key 1",
            encrypted_key=encryption_manager.encrypt("api_key_1"),
            coral_session_id="session_1"
        )
        
        key2 = StoredKey.create_new(
            owner_id=owner_id,
            key_name="Key 2",
            encrypted_key=encryption_manager.encrypt("api_key_2"),
            coral_session_id="session_2"
        )
        
        # Create key for different owner
        key3 = StoredKey.create_new(
            owner_id="different_owner",
            key_name="Key 3",
            encrypted_key=encryption_manager.encrypt("api_key_3"),
            coral_session_id="session_3"
        )
        
        # Store all keys
        await storage_service.store_key(key1)
        await storage_service.store_key(key2)
        await storage_service.store_key(key3)
        
        # Get keys for first owner
        owner_keys = await storage_service.get_keys_by_owner(owner_id)
        assert len(owner_keys) == 2
        
        key_ids = [key.key_id for key in owner_keys]
        assert key1.key_id in key_ids
        assert key2.key_id in key_ids
        assert key3.key_id not in key_ids
    
    @pytest.mark.asyncio
    async def test_get_keys_by_owner_active_only(self, storage_service, encryption_manager):
        """Test retrieving only active keys by owner"""
        owner_id = "coral_user_123"
        
        # Create active key
        active_key = StoredKey.create_new(
            owner_id=owner_id,
            key_name="Active Key",
            encrypted_key=encryption_manager.encrypt("api_key_1"),
            coral_session_id="session_1"
        )
        
        # Create inactive key
        inactive_key = StoredKey.create_new(
            owner_id=owner_id,
            key_name="Inactive Key",
            encrypted_key=encryption_manager.encrypt("api_key_2"),
            coral_session_id="session_2"
        )
        inactive_key.is_active = False
        
        # Store both keys
        await storage_service.store_key(active_key)
        await storage_service.store_key(inactive_key)
        
        # Get active keys only
        active_keys = await storage_service.get_keys_by_owner(owner_id, active_only=True)
        assert len(active_keys) == 1
        assert active_keys[0].key_id == active_key.key_id
        
        # Get all keys
        all_keys = await storage_service.get_keys_by_owner(owner_id, active_only=False)
        assert len(all_keys) == 2
    
    @pytest.mark.asyncio
    async def test_update_key(self, storage_service, sample_stored_key):
        """Test updating existing key"""
        # Store key first
        await storage_service.store_key(sample_stored_key)
        
        # Update key name
        sample_stored_key.key_name = "Updated Key Name"
        sample_stored_key.last_rotated = datetime.utcnow()
        
        result = await storage_service.update_key(sample_stored_key)
        assert result is True
        
        # Verify update
        retrieved = await storage_service.get_key(sample_stored_key.key_id)
        assert retrieved.key_name == "Updated Key Name"
    
    @pytest.mark.asyncio
    async def test_update_key_not_exists(self, storage_service, sample_stored_key):
        """Test updating non-existent key"""
        result = await storage_service.update_key(sample_stored_key)
        assert result is False
    
    @pytest.mark.asyncio
    async def test_delete_key(self, storage_service, sample_stored_key):
        """Test deleting key"""
        # Store key first
        await storage_service.store_key(sample_stored_key)
        
        # Delete it
        result = await storage_service.delete_key(sample_stored_key.key_id)
        assert result is True
        
        # Verify it's gone
        retrieved = await storage_service.get_key(sample_stored_key.key_id)
        assert retrieved is None
    
    @pytest.mark.asyncio
    async def test_delete_key_not_exists(self, storage_service):
        """Test deleting non-existent key"""
        result = await storage_service.delete_key("non_existent_key")
        assert result is False
    
    @pytest.mark.asyncio
    async def test_deactivate_key(self, storage_service, sample_stored_key):
        """Test deactivating key"""
        # Store key first
        await storage_service.store_key(sample_stored_key)
        
        # Deactivate it
        result = await storage_service.deactivate_key(sample_stored_key.key_id)
        assert result is True
        
        # Verify it's deactivated
        retrieved = await storage_service.get_key(sample_stored_key.key_id)
        assert retrieved is not None
        assert retrieved.is_active is False
    
    @pytest.mark.asyncio
    async def test_deactivate_key_not_exists(self, storage_service):
        """Test deactivating non-existent key"""
        result = await storage_service.deactivate_key("non_existent_key")
        assert result is False
    
    @pytest.mark.asyncio
    async def test_verify_key_ownership(self, storage_service, sample_stored_key):
        """Test verifying key ownership"""
        # Store key first
        await storage_service.store_key(sample_stored_key)
        
        # Verify correct owner
        result = await storage_service.verify_key_ownership(
            sample_stored_key.key_id, 
            sample_stored_key.owner_id
        )
        assert result is True
        
        # Verify incorrect owner
        result = await storage_service.verify_key_ownership(
            sample_stored_key.key_id, 
            "different_owner"
        )
        assert result is False
        
        # Verify non-existent key
        result = await storage_service.verify_key_ownership(
            "non_existent_key", 
            sample_stored_key.owner_id
        )
        assert result is False
    
    def test_get_storage_stats(self, storage_service, sample_stored_key):
        """Test getting storage statistics"""
        # Initial stats
        stats = storage_service.get_storage_stats()
        assert stats['total_keys'] == 0
        assert stats['active_keys'] == 0
        assert stats['unique_owners'] == 0
        assert stats['database_exists'] is True
        
        # Add a key and check stats
        asyncio.run(storage_service.store_key(sample_stored_key))
        
        stats = storage_service.get_storage_stats()
        assert stats['total_keys'] == 1
        assert stats['active_keys'] == 1
        assert stats['unique_owners'] == 1


if __name__ == "__main__":
    pytest.main([__file__])