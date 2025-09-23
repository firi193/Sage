"""
AccessGrant data model for managing API key access permissions
"""

from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, Any
import uuid


@dataclass
class AccessGrant:
    """
    Represents an access grant allowing a caller to use a specific API key
    
    Attributes:
        grant_id: Unique identifier for the grant
        key_id: ID of the key this grant applies to
        caller_id: Coral wallet/session ID of the caller
        permissions: Dictionary containing permission settings (e.g., max_calls_per_day)
        created_at: Timestamp when grant was created
        expires_at: Timestamp when grant expires
        is_active: Whether the grant is currently active
        granted_by: Owner's Coral ID who granted access
    """
    grant_id: str
    key_id: str
    caller_id: str
    permissions: Dict[str, Any]
    created_at: datetime
    expires_at: datetime
    is_active: bool
    granted_by: str

    @classmethod
    def create_new(cls, key_id: str, caller_id: str, permissions: Dict[str, Any],
                   expires_at: datetime, granted_by: str) -> 'AccessGrant':
        """Create a new AccessGrant instance with generated ID and timestamp"""
        return cls(
            grant_id=str(uuid.uuid4()),
            key_id=key_id,
            caller_id=caller_id,
            permissions=permissions.copy(),
            created_at=datetime.utcnow(),
            expires_at=expires_at,
            is_active=True,
            granted_by=granted_by
        )

    def validate(self) -> bool:
        """Validate the AccessGrant instance"""
        if not self.grant_id or not isinstance(self.grant_id, str):
            return False
        if not self.key_id or not isinstance(self.key_id, str):
            return False
        if not self.caller_id or not isinstance(self.caller_id, str):
            return False
        if not isinstance(self.permissions, dict):
            return False
        if not isinstance(self.created_at, datetime):
            return False
        if not isinstance(self.expires_at, datetime):
            return False
        if not isinstance(self.is_active, bool):
            return False
        if not self.granted_by or not isinstance(self.granted_by, str):
            return False
        # Validate that expires_at is after created_at
        if self.expires_at <= self.created_at:
            return False
        return True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        data = asdict(self)
        # Convert datetime objects to ISO format strings
        data['created_at'] = self.created_at.isoformat()
        data['expires_at'] = self.expires_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AccessGrant':
        """Create AccessGrant from dictionary"""
        # Convert ISO format strings back to datetime objects
        data['created_at'] = datetime.fromisoformat(data['created_at'])
        data['expires_at'] = datetime.fromisoformat(data['expires_at'])
        return cls(**data)

    def is_expired(self) -> bool:
        """Check if the grant has expired"""
        return datetime.utcnow() > self.expires_at

    def is_valid(self) -> bool:
        """Check if the grant is valid (active and not expired)"""
        return self.is_active and not self.is_expired()

    def revoke(self) -> None:
        """Revoke the access grant"""
        self.is_active = False

    def get_max_calls_per_day(self) -> int:
        """Get the maximum calls per day from permissions"""
        return self.permissions.get('max_calls_per_day', 0)

    def update_permissions(self, new_permissions: Dict[str, Any]) -> None:
        """Update the permissions for this grant"""
        self.permissions.update(new_permissions)