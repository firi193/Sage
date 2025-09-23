"""
PrivacyAuditLog data model for privacy-conscious audit logging
"""

from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, Any, Optional
import uuid


@dataclass
class PrivacyAuditLog:
    """
    Represents a privacy-conscious audit log entry that records metadata only
    
    Attributes:
        log_id: Unique identifier for the log entry
        timestamp: When the action occurred
        caller_id: Coral wallet/session ID of the caller
        key_id: ID of the key used
        action: Type of action performed (e.g., "proxy_call", "grant_access")
        method: HTTP method for API calls
        endpoint: Target API endpoint
        payload_size: Size of payload in bytes (not content)
        response_time: Response time in milliseconds
        response_code: HTTP response code
        error_message: Error message if action failed
    """
    log_id: str
    timestamp: datetime
    caller_id: str
    key_id: str
    action: str
    method: str
    endpoint: str
    payload_size: int
    response_time: float
    response_code: int
    error_message: Optional[str] = None

    @classmethod
    def create_new(cls, caller_id: str, key_id: str, action: str, method: str,
                   endpoint: str, payload_size: int, response_time: float,
                   response_code: int, error_message: Optional[str] = None) -> 'PrivacyAuditLog':
        """Create a new PrivacyAuditLog instance with generated ID and timestamp"""
        return cls(
            log_id=str(uuid.uuid4()),
            timestamp=datetime.utcnow(),
            caller_id=caller_id,
            key_id=key_id,
            action=action,
            method=method,
            endpoint=endpoint,
            payload_size=payload_size,
            response_time=response_time,
            response_code=response_code,
            error_message=error_message
        )

    def validate(self) -> bool:
        """Validate the PrivacyAuditLog instance"""
        if not self.log_id or not isinstance(self.log_id, str):
            return False
        if not isinstance(self.timestamp, datetime):
            return False
        if not self.caller_id or not isinstance(self.caller_id, str):
            return False
        if not self.key_id or not isinstance(self.key_id, str):
            return False
        if not self.action or not isinstance(self.action, str):
            return False
        if not self.method or not isinstance(self.method, str):
            return False
        if not self.endpoint or not isinstance(self.endpoint, str):
            return False
        if not isinstance(self.payload_size, int) or self.payload_size < 0:
            return False
        if not isinstance(self.response_time, (int, float)) or self.response_time < 0:
            return False
        if not isinstance(self.response_code, int):
            return False
        if self.error_message is not None and not isinstance(self.error_message, str):
            return False
        return True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        data = asdict(self)
        # Convert datetime object to ISO format string
        data['timestamp'] = self.timestamp.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PrivacyAuditLog':
        """Create PrivacyAuditLog from dictionary"""
        # Convert ISO format string back to datetime object
        data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        return cls(**data)

    def is_error(self) -> bool:
        """Check if this log entry represents an error"""
        return self.error_message is not None or self.response_code >= 400

    def is_rate_limit_error(self) -> bool:
        """Check if this log entry represents a rate limit error"""
        return self.response_code == 429 or (
            self.error_message and "rate limit" in self.error_message.lower()
        )

    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics from this log entry"""
        return {
            'response_time': self.response_time,
            'payload_size': self.payload_size,
            'response_code': self.response_code
        }