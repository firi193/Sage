"""
StoredKey data model for encrypted API key storage
"""

from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, Any
import uuid


@dataclass
class StoredKey:
    """
    Represents an encrypted API key stored in Sage
    
    Attributes:
        key_id: Unique identifier for the key
        owner_id: Coral wallet/session ID of the key owner
        key_name: Human-readable name for the key
        encrypted_key: Encrypted API key bytes
        created_at: Timestamp when key was created
        last_rotated: Timestamp when key was last rotated
        is_active: Whether the key is currently active
        coral_session_id: Coral session ID for authentication
    """
    key_id: str
    owner_id: str
    key_name: str
    encrypted_key: bytes
    created_at: datetime
    last_rotated: datetime
    is_active: bool
    coral_session_id: str

    @classmethod
    def create_new(cls, owner_id: str, key_name: str, encrypted_key: bytes, 
                   coral_session_id: str) -> 'StoredKey':
        """Create a new StoredKey instance with generated ID and timestamps"""
        now = datetime.utcnow()
        return cls(
            key_id=str(uuid.uuid4()),
            owner_id=owner_id,
            key_name=key_name,
            encrypted_key=encrypted_key,
            created_at=now,
            last_rotated=now,
            is_active=True,
            coral_session_id=coral_session_id
        )

    def validate(self) -> bool:
        """Validate the StoredKey instance"""
        if not self.key_id or not isinstance(self.key_id, str):
            return False
        if not self.owner_id or not isinstance(self.owner_id, str):
            return False
        if not self.key_name or not isinstance(self.key_name, str):
            return False
        if not self.encrypted_key or not isinstance(self.encrypted_key, bytes):
            return False
        if not isinstance(self.created_at, datetime):
            return False
        if not isinstance(self.last_rotated, datetime):
            return False
        if not isinstance(self.is_active, bool):
            return False
        if not self.coral_session_id or not isinstance(self.coral_session_id, str):
            return False
        return True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        data = asdict(self)
        # Convert datetime objects to ISO format strings
        data['created_at'] = self.created_at.isoformat()
        data['last_rotated'] = self.last_rotated.isoformat()
        # Convert bytes to base64 string for JSON serialization
        import base64
        data['encrypted_key'] = base64.b64encode(self.encrypted_key).decode('utf-8')
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'StoredKey':
        """Create StoredKey from dictionary"""
        import base64
        # Convert ISO format strings back to datetime objects
        data['created_at'] = datetime.fromisoformat(data['created_at'])
        data['last_rotated'] = datetime.fromisoformat(data['last_rotated'])
        # Convert base64 string back to bytes
        data['encrypted_key'] = base64.b64decode(data['encrypted_key'])
        return cls(**data)

    def rotate_key(self, new_encrypted_key: bytes) -> None:
        """Update the encrypted key and rotation timestamp"""
        self.encrypted_key = new_encrypted_key
        self.last_rotated = datetime.utcnow()

    def deactivate(self) -> None:
        """Mark the key as inactive"""
        self.is_active = False