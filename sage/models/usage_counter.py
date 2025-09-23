"""
UsageCounter data model for tracking API usage per caller per key
"""

from dataclasses import dataclass, asdict
from datetime import datetime, date
from typing import Dict, Any


@dataclass
class UsageCounter:
    """
    Represents usage statistics for a specific caller and key combination
    
    Attributes:
        key_id: ID of the key being tracked
        caller_id: Coral wallet/session ID of the caller
        date: Date for which usage is tracked
        call_count: Number of API calls made
        total_payload_size: Total size of all payloads in bytes
        average_response_time: Average response time in milliseconds
        last_reset: Timestamp when counter was last reset
    """
    key_id: str
    caller_id: str
    date: date
    call_count: int
    total_payload_size: int
    average_response_time: float
    last_reset: datetime

    @classmethod
    def create_new(cls, key_id: str, caller_id: str, target_date: date = None) -> 'UsageCounter':
        """Create a new UsageCounter instance for today or specified date"""
        if target_date is None:
            target_date = date.today()
        
        return cls(
            key_id=key_id,
            caller_id=caller_id,
            date=target_date,
            call_count=0,
            total_payload_size=0,
            average_response_time=0.0,
            last_reset=datetime.utcnow()
        )

    def validate(self) -> bool:
        """Validate the UsageCounter instance"""
        if not self.key_id or not isinstance(self.key_id, str):
            return False
        if not self.caller_id or not isinstance(self.caller_id, str):
            return False
        if not isinstance(self.date, date):
            return False
        if not isinstance(self.call_count, int) or self.call_count < 0:
            return False
        if not isinstance(self.total_payload_size, int) or self.total_payload_size < 0:
            return False
        if not isinstance(self.average_response_time, (int, float)) or self.average_response_time < 0:
            return False
        if not isinstance(self.last_reset, datetime):
            return False
        return True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        data = asdict(self)
        # Convert date and datetime objects to ISO format strings
        data['date'] = self.date.isoformat()
        data['last_reset'] = self.last_reset.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UsageCounter':
        """Create UsageCounter from dictionary"""
        # Convert ISO format strings back to date and datetime objects
        data['date'] = date.fromisoformat(data['date'])
        data['last_reset'] = datetime.fromisoformat(data['last_reset'])
        return cls(**data)

    def increment_usage(self, payload_size: int, response_time: float) -> None:
        """Increment usage counters with new call data"""
        # Update average response time using incremental formula
        if self.call_count == 0:
            self.average_response_time = response_time
        else:
            total_time = self.average_response_time * self.call_count
            total_time += response_time
            self.average_response_time = total_time / (self.call_count + 1)
        
        # Increment counters
        self.call_count += 1
        self.total_payload_size += payload_size

    def reset_daily_counter(self) -> None:
        """Reset the counter for a new day"""
        self.call_count = 0
        self.total_payload_size = 0
        self.average_response_time = 0.0
        self.last_reset = datetime.utcnow()

    def is_today(self) -> bool:
        """Check if this counter is for today's date"""
        return self.date == date.today()

    def get_usage_summary(self) -> Dict[str, Any]:
        """Get a summary of usage statistics"""
        return {
            'key_id': self.key_id,
            'caller_id': self.caller_id,
            'date': self.date.isoformat(),
            'call_count': self.call_count,
            'total_payload_size': self.total_payload_size,
            'average_response_time': self.average_response_time,
            'last_reset': self.last_reset.isoformat()
        }