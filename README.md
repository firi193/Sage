# Sage MVP - Secure API Key Management for Coral Agents

Sage is a Coral Agent that provides secure API key usage, proxying, and traceability for other agents on the Internet of Agents (IoA). The system eliminates the need for agents to share API keys directly while providing comprehensive tracking, access control, and policy enforcement.

## Project Structure

```
sage/
├── __init__.py                 # Package initialization
├── models/                     # Core data models
│   ├── __init__.py
│   ├── stored_key.py          # StoredKey model for encrypted API keys
│   ├── access_grant.py        # AccessGrant model for permissions
│   ├── privacy_audit_log.py   # PrivacyAuditLog model for audit trails
│   └── usage_counter.py       # UsageCounter model for rate limiting
├── services/                   # Core services (to be implemented)
│   └── __init__.py
└── utils/                      # Utility functions (to be implemented)
    └── __init__.py

tests/
├── __init__.py
└── test_models.py             # Unit tests for data models

requirements.txt               # Python dependencies
setup.py                      # Package setup configuration
validate_models.py            # Model validation script
README.md                     # This file
```

## Core Data Models

### StoredKey
Represents an encrypted API key stored in Sage with the following features:
- Unique key_id for reference
- Encrypted storage (never plaintext)
- Owner identification via Coral session/wallet ID
- Key rotation and lifecycle management
- Validation and serialization methods

### AccessGrant
Manages access permissions for API keys with:
- Grant-based access control
- Expiration handling
- Permission settings (e.g., max_calls_per_day)
- Automatic cleanup of expired grants
- Validation and serialization methods

### PrivacyAuditLog
Privacy-conscious audit logging that records:
- Metadata only (no full payloads for privacy)
- Performance metrics (response time, payload size)
- Tamper-resistant chronological logging
- Error tracking and rate limit detection
- Validation and serialization methods

### UsageCounter
Tracks API usage per caller per key with:
- Daily usage counters
- Rate limit enforcement
- Performance statistics
- Automatic daily resets
- Validation and serialization methods

## Requirements Addressed

This implementation addresses the following requirements from the specification:

- **Requirement 1.3**: Unique key_id assignment for stored keys
- **Requirement 2.1**: Grant creation with key_id, caller_agent_id, permissions, and expiry
- **Requirement 4.1**: Comprehensive logging with metadata only for privacy

## Installation

1. Install Python dependencies:
```bash
pip install -r requirements.txt
```

2. Validate the models:
```bash
python validate_models.py
```

## Next Steps

The core data models are now implemented and validated. The next tasks in the implementation plan will build upon these models to create:

1. Encryption and key storage foundation
2. Key Management Service
3. Authorization Engine
4. Policy Engine for rate limiting
5. Privacy-Aware Logging Service
6. Coral MCP Interface with integrated proxy

## Testing

Run the model validation script to ensure all core data models are working correctly:

```bash
python validate_models.py
```

This will test all four core models and their validation, serialization, and business logic methods.