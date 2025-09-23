"""
Key Management Service for Sage - handles secure API key lifecycle operations
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
import logging

from ..models.stored_key import StoredKey
from ..utils.encryption import EncryptionManager, validate_api_key
from .key_storage import KeyStorageService


logger = logging.getLogger(__name__)


class KeyManager:
    """
    High-level key management service that orchestrates key lifecycle operations
    Provides secure storage, retrieval, rotation, and revocation of API keys
    """
    
    def __init__(self, storage_service: KeyStorageService = None, 
                 encryption_manager: EncryptionManager = None):
        """
        Initialize KeyManager with storage and encryption services
        
        Args:
            storage_service: Storage service for key persistence
            encryption_manager: Encryption manager for key protection
        """
        self.storage_service = storage_service or KeyStorageService()
        self.encryption_manager = encryption_manager or EncryptionManager()
    
    async def store_key(self, key_name: str, api_key: str, owner_id: str, 
                       coral_session_id: str) -> str:
        """
        Encrypt and store a new API key
        
        Args:
            key_name: Human-readable name for the key
            api_key: The actual API key to encrypt and store
            owner_id: Coral wallet/session ID of the key owner
            coral_session_id: Coral session ID for authentication
            
        Returns:
            key_id: Unique identifier for the stored key
            
        Raises:
            ValueError: If API key is invalid or key name already exists for owner
            RuntimeError: If storage operation fails
        """
        # Validate API key format
        if not validate_api_key(api_key):
            raise ValueError("Invalid API key format")
        
        if not key_name or not key_name.strip():
            raise ValueError("Key name cannot be empty")
        
        if not owner_id or not owner_id.strip():
            raise ValueError("Owner ID cannot be empty")
        
        if not coral_session_id or not coral_session_id.strip():
            raise ValueError("Coral session ID cannot be empty")
        
        # Check if key name already exists for this owner
        existing_keys = self.storage_service.get_keys_by_owner(owner_id, active_only=True)
        if any(key.key_name == key_name for key in existing_keys):
            raise ValueError(f"Key name '{key_name}' already exists for owner")
        
        try:
            # Encrypt the API key
            encrypted_key = self.encryption_manager.encrypt(api_key)
            
            # Create StoredKey instance
            stored_key = StoredKey.create_new(
                owner_id=owner_id,
                key_name=key_name,
                encrypted_key=encrypted_key,
                coral_session_id=coral_session_id
            )
            
            # Store in database
            success = self.storage_service.store_key(stored_key)
            if not success:
                raise RuntimeError("Failed to store key in database")
            
            logger.info(f"Successfully stored key '{key_name}' for owner {owner_id}")
            return stored_key.key_id
            
        except Exception as e:
            logger.error(f"Failed to store key '{key_name}' for owner {owner_id}: {str(e)}")
            raise RuntimeError(f"Key storage failed: {str(e)}")
    
    async def _retrieve_key_for_proxy(self, key_id: str) -> str:
        """
        Retrieve and decrypt API key for proxy operations
        This is an internal method used by the proxy service
        
        Args:
            key_id: Unique key identifier
            
        Returns:
            Decrypted API key string
            
        Raises:
            ValueError: If key not found or inactive
            RuntimeError: If decryption fails
        """
        try:
            # Retrieve stored key
            stored_key = self.storage_service.get_key(key_id)
            if not stored_key:
                raise ValueError(f"Key not found: {key_id}")
            
            if not stored_key.is_active:
                raise ValueError(f"Key is inactive: {key_id}")
            
            # Decrypt the API key
            api_key = self.encryption_manager.decrypt(stored_key.encrypted_key)
            
            logger.debug(f"Successfully retrieved key for proxy: {key_id}")
            return api_key
            
        except ValueError:
            # Re-raise validation errors
            raise
        except Exception as e:
            logger.error(f"Failed to retrieve key for proxy {key_id}: {str(e)}")
            raise RuntimeError(f"Key retrieval failed: {str(e)}")
    
    async def list_keys(self, owner_id: str) -> List[Dict[str, Any]]:
        """
        List all keys for an owner (metadata only, no actual key values)
        
        Args:
            owner_id: Coral wallet/session ID of the key owner
            
        Returns:
            List of key metadata dictionaries
        """
        if not owner_id or not owner_id.strip():
            raise ValueError("Owner ID cannot be empty")
        
        try:
            stored_keys = self.storage_service.get_keys_by_owner(owner_id, active_only=True)
            
            # Return metadata only, never expose actual keys
            key_list = []
            for stored_key in stored_keys:
                key_list.append({
                    'key_id': stored_key.key_id,
                    'key_name': stored_key.key_name,
                    'created_at': stored_key.created_at.isoformat(),
                    'last_rotated': stored_key.last_rotated.isoformat(),
                    'is_active': stored_key.is_active
                })
            
            logger.debug(f"Listed {len(key_list)} keys for owner {owner_id}")
            return key_list
            
        except Exception as e:
            logger.error(f"Failed to list keys for owner {owner_id}: {str(e)}")
            raise RuntimeError(f"Key listing failed: {str(e)}")
    
    async def rotate_key(self, key_id: str, new_api_key: str, owner_id: str) -> bool:
        """
        Rotate an existing API key with a new value
        
        Args:
            key_id: Unique key identifier
            new_api_key: New API key to replace the old one
            owner_id: Coral wallet/session ID of the key owner
            
        Returns:
            True if rotation successful, False otherwise
            
        Raises:
            ValueError: If key not found, owner mismatch, or invalid new key
            RuntimeError: If rotation operation fails
        """
        # Validate new API key
        if not validate_api_key(new_api_key):
            raise ValueError("Invalid new API key format")
        
        if not owner_id or not owner_id.strip():
            raise ValueError("Owner ID cannot be empty")
        
        try:
            # Verify key exists and ownership
            if not self.storage_service.verify_key_ownership(key_id, owner_id):
                raise ValueError("Key not found or access denied")
            
            # Retrieve current key
            stored_key = self.storage_service.get_key(key_id)
            if not stored_key:
                raise ValueError(f"Key not found: {key_id}")
            
            if not stored_key.is_active:
                raise ValueError(f"Cannot rotate inactive key: {key_id}")
            
            # Encrypt new API key
            new_encrypted_key = self.encryption_manager.encrypt(new_api_key)
            
            # Update the stored key
            stored_key.rotate_key(new_encrypted_key)
            
            # Save to database
            success = self.storage_service.update_key(stored_key)
            if not success:
                raise RuntimeError("Failed to update key in database")
            
            logger.info(f"Successfully rotated key {key_id} for owner {owner_id}")
            return True
            
        except ValueError:
            # Re-raise validation errors
            raise
        except Exception as e:
            logger.error(f"Failed to rotate key {key_id} for owner {owner_id}: {str(e)}")
            raise RuntimeError(f"Key rotation failed: {str(e)}")
    
    async def revoke_key(self, key_id: str, owner_id: str) -> bool:
        """
        Revoke (deactivate) an API key
        
        Args:
            key_id: Unique key identifier
            owner_id: Coral wallet/session ID of the key owner
            
        Returns:
            True if revocation successful, False otherwise
            
        Raises:
            ValueError: If key not found or owner mismatch
            RuntimeError: If revocation operation fails
        """
        if not owner_id or not owner_id.strip():
            raise ValueError("Owner ID cannot be empty")
        
        try:
            # Verify key exists and ownership
            if not self.storage_service.verify_key_ownership(key_id, owner_id):
                raise ValueError("Key not found or access denied")
            
            # Deactivate the key
            success = self.storage_service.deactivate_key(key_id)
            if not success:
                raise RuntimeError("Failed to deactivate key in database")
            
            logger.info(f"Successfully revoked key {key_id} for owner {owner_id}")
            return True
            
        except ValueError:
            # Re-raise validation errors
            raise
        except Exception as e:
            logger.error(f"Failed to revoke key {key_id} for owner {owner_id}: {str(e)}")
            raise RuntimeError(f"Key revocation failed: {str(e)}")
    
    async def verify_key_ownership(self, key_id: str, owner_id: str) -> bool:
        """
        Verify that a key belongs to the specified owner
        
        Args:
            key_id: Unique key identifier
            owner_id: Coral wallet/session ID of the key owner
            
        Returns:
            True if owner matches, False otherwise
        """
        if not owner_id or not owner_id.strip():
            return False
        
        try:
            return self.storage_service.verify_key_ownership(key_id, owner_id)
        except Exception as e:
            logger.error(f"Failed to verify key ownership {key_id} for owner {owner_id}: {str(e)}")
            return False
    
    async def get_key_metadata(self, key_id: str, owner_id: str) -> Optional[Dict[str, Any]]:
        """
        Get metadata for a specific key (no actual key value)
        
        Args:
            key_id: Unique key identifier
            owner_id: Coral wallet/session ID of the key owner
            
        Returns:
            Key metadata dictionary if found and owned by user, None otherwise
        """
        if not owner_id or not owner_id.strip():
            return None
        
        try:
            # Verify ownership first
            if not self.storage_service.verify_key_ownership(key_id, owner_id):
                return None
            
            stored_key = self.storage_service.get_key(key_id)
            if not stored_key:
                return None
            
            return {
                'key_id': stored_key.key_id,
                'key_name': stored_key.key_name,
                'created_at': stored_key.created_at.isoformat(),
                'last_rotated': stored_key.last_rotated.isoformat(),
                'is_active': stored_key.is_active,
                'owner_id': stored_key.owner_id
            }
            
        except Exception as e:
            logger.error(f"Failed to get key metadata {key_id} for owner {owner_id}: {str(e)}")
            return None