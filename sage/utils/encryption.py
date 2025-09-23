"""
Encryption utilities for secure API key storage using AES-256
"""

import os
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from typing import Union


class EncryptionManager:
    """
    Handles AES-256 encryption and decryption for API keys
    Uses Fernet (AES-256 in CBC mode with HMAC for authentication)
    """
    
    def __init__(self, master_key: str = None):
        """
        Initialize encryption manager with master key
        
        Args:
            master_key: Master key for encryption. If None, generates a new one.
        """
        if master_key:
            self._key = self._derive_key_from_password(master_key)
        else:
            self._key = Fernet.generate_key()
        self._fernet = Fernet(self._key)
    
    def _derive_key_from_password(self, password: str, salt: bytes = None) -> bytes:
        """
        Derive encryption key from password using PBKDF2
        
        Args:
            password: Master password
            salt: Salt for key derivation. If None, uses fixed salt for consistency
            
        Returns:
            Derived encryption key
        """
        if salt is None:
            # Use a fixed salt for consistency - in production, this should be configurable
            salt = b'sage_encryption_salt_v1'
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return key
    
    def encrypt(self, plaintext: str) -> bytes:
        """
        Encrypt plaintext string to bytes
        
        Args:
            plaintext: String to encrypt
            
        Returns:
            Encrypted bytes
        """
        if not isinstance(plaintext, str):
            raise ValueError("Plaintext must be a string")
        
        return self._fernet.encrypt(plaintext.encode('utf-8'))
    
    def decrypt(self, encrypted_data: bytes) -> str:
        """
        Decrypt bytes to plaintext string
        
        Args:
            encrypted_data: Encrypted bytes to decrypt
            
        Returns:
            Decrypted plaintext string
        """
        if not isinstance(encrypted_data, bytes):
            raise ValueError("Encrypted data must be bytes")
        
        decrypted_bytes = self._fernet.decrypt(encrypted_data)
        return decrypted_bytes.decode('utf-8')
    
    def get_key_b64(self) -> str:
        """
        Get the encryption key as base64 string for storage
        
        Returns:
            Base64 encoded encryption key
        """
        return base64.urlsafe_b64encode(self._key).decode('utf-8')
    
    @classmethod
    def from_key_b64(cls, key_b64: str) -> 'EncryptionManager':
        """
        Create EncryptionManager from base64 encoded key
        
        Args:
            key_b64: Base64 encoded encryption key
            
        Returns:
            EncryptionManager instance
        """
        key = base64.urlsafe_b64decode(key_b64.encode('utf-8'))
        manager = cls.__new__(cls)
        manager._key = key
        manager._fernet = Fernet(key)
        return manager


def generate_master_key() -> str:
    """
    Generate a new master key for encryption
    
    Returns:
        Base64 encoded master key
    """
    key = Fernet.generate_key()
    return base64.urlsafe_b64encode(key).decode('utf-8')


def validate_api_key(api_key: str) -> bool:
    """
    Validate API key format and basic requirements
    
    Args:
        api_key: API key to validate
        
    Returns:
        True if valid, False otherwise
    """
    if not isinstance(api_key, str):
        return False
    
    # Basic validation - API key should be non-empty and reasonable length
    if not api_key or len(api_key.strip()) == 0:
        return False
    
    # Most API keys are between 16 and 512 characters
    if len(api_key) < 8 or len(api_key) > 512:
        return False
    
    # Should not contain control characters
    if any(ord(c) < 32 for c in api_key):
        return False
    
    return True