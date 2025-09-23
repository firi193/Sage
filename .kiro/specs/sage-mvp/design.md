# Design Document

## Overview

Sage is implemented as a Python-based Coral Agent that provides secure API key management and proxying services through Coral's MCP protocol interface. The system uses a layered architecture with clear separation between authentication, key management, proxying, and logging concerns. The design prioritizes security through encryption at rest, zero key sharing, privacy-conscious logging, and comprehensive audit trails while maintaining full compatibility with the Coral ecosystem.

## Architecture

### 1. High-Level Architecture
mermaid
graph TB
```
    A[Calling Agent] -->|Coral MCP Request| B[Sage Coral Interface]
    B --> C[Coral Session & Auth]
    C --> D[Access Control / Grant Engine]
    D --> E[Key Injection Proxy]
    E --> F[External API]

    C --> G[Key Management & Encrypted Storage]
    E --> H[Audit Logging & Policy Enforcement]
```

Flow Explanation:

1. Calling Agent sends a request via Coral MCP.
2. Sage Coral Interface handles protocol compliance and routes requests.
3. Coral Session & Auth validates session/wallet IDs.
4. Access Control / Grant Engine checks whether the caller is authorized for the requested key and policy constraints.
5. Key Injection Proxy injects the actual API key and forwards the request to the external API.
6. Key Management & Encrypted Storage handles secure storage and key rotation.
7. Audit Logging & Policy Enforcement logs requests, enforces rate limits, and tracks usage.



Component Layers (MVP)

1. Coral MCP Interface – handles incoming Coral requests, ensures MCP compliance.
2. Authentication Layer – verifies caller identity via Coral sessions.
3. Access Control Layer – validates grants, permissions, and policies.
4. Proxy Layer – injects API keys and forwards requests.
5. Storage Layer – stores API keys encrypted and maintains metadata.
6. Audit & Policy Layer – logs calls, enforces rate limits, revokes expired or misused access.


Core Interfaces (Python-style MVP)
```
class SageMCP:
    # Agent-facing methods
    def add_key(self, key_name: str, api_key: str, owner_session: str) -> str:
        """Encrypts and stores a new API key, returns key_id"""
    
    def grant_access(self, key_id: str, caller_id: str, permissions: dict, expiry: int, owner_session: str) -> bool:
        """Creates a grant for another agent with permissions and expiry"""
    
    def proxy_call(self, key_id: str, target_url: str, payload: dict, caller_session: str) -> dict:
        """Injects API key, enforces policy, forwards request, returns response"""

    def list_logs(self, key_id: str, filters: dict, owner_session: str) -> list:
        """Returns filtered audit logs for the key owner"""

```

Notes for MVP:

    proxy_call internally enforces rate limits, policy checks, and logging before calling the external API.

    All session/auth validation relies on Coral MCP sessions/wallet IDs.

    Logs are tamper-resistant and filterable by key, caller, and time range.

    MVP does not include advanced delegation frameworks, but leaves hooks for future expansion.

    Focus is on plug-and-play for other Coral agents, no infra-specific integrations required.




### 2. Key Management Service

**Responsibilities:**
- Encrypt and store API keys
- Manage key lifecycle (create, rotate, revoke)
- Provide secure key retrieval for proxying
- Validate key ownership through Coral identity

**Key Methods:**
```python
class KeyManager:
    async def store_key(self, key_name: str, api_key: str, owner_id: str) -> str
    async def _retrieve_key_for_proxy(self, key_id: str) -> str
    async def rotate_key(self, key_id: str, new_key: str, owner_id: str) -> bool
    async def revoke_key(self, key_id: str, owner_id: str) -> bool
    async def list_keys(self, owner_id: str) -> list
    async def verify_key_ownership(self, key_id: str, owner_id: str) -> bool
```

### 3. Authorization Engine

**Responsibilities:**
- Manage access grants and permissions
- Validate caller authorization for key usage
- Handle grant expiration and revocation
- Integrate with Coral identity system

**Key Methods:**
```python
class AuthorizationEngine:
    async def create_grant(self, key_id: str, caller_id: str, permissions: dict, expiry: datetime, owner_id: str) -> str
    async def check_authorization(self, key_id: str, caller_session: str) -> bool
    async def revoke_grant(self, grant_id: str, owner_id: str) -> bool
    async def cleanup_expired_grants(self) -> int
    async def validate_coral_identity(self, session_id: str, wallet_id: str) -> str
```

### 4. Proxy Service

**Responsibilities:**
- Forward API requests with key injection
- Handle HTTP/HTTPS communication
- Manage request/response transformation
- Track performance metrics (response time, payload sizes)

**Key Methods:**
```python
class ProxyService:
    async def make_proxied_call(self, key_id: str, target_url: str, payload: dict, caller_session: str) -> dict
    async def inject_api_key(self, request: dict, api_key: str) -> dict
    async def forward_request(self, url: str, method: str, headers: dict, body: dict) -> tuple[dict, float]
    async def measure_performance(self, start_time: float, payload_size: int) -> dict
```

### 5. Policy Engine

**Responsibilities:**
- Enforce rate limits and usage policies
- Track usage counters per caller per key
- Block requests that violate policies
- Apply policy changes immediately

**Key Methods:**
```python
class PolicyEngine:
    async def check_rate_limit(self, key_id: str, caller_id: str) -> bool
    async def increment_usage(self, key_id: str, caller_id: str) -> None
    async def reset_daily_counters(self) -> None
    async def update_policy(self, key_id: str, policy: dict, owner_id: str) -> bool
    async def get_current_usage(self, key_id: str, caller_id: str) -> int
```

### 6. Privacy-Aware Logging Service

**Responsibilities:**
- Record API calls with privacy-conscious metadata (no full payloads)
- Track performance metrics (response times, payload sizes)
- Provide audit trail functionality
- Support log querying and filtering
- Ensure tamper-resistant chronological logging

**Key Methods:**
```python
class PrivacyAwareLoggingService:
    async def log_api_call(self, caller_id: str, key_id: str, method: str, endpoint: str, 
                          payload_size: int, response_time: float, response_code: int) -> None
    async def log_rate_limit_hit(self, caller_id: str, key_id: str, current_usage: int, limit: int) -> None
    async def log_system_event(self, event_type: str, details: dict) -> None
    async def query_logs(self, filters: dict, requester_id: str) -> list
    async def get_usage_stats(self, key_id: str, time_range: tuple, owner_id: str) -> dict
    async def verify_log_integrity(self) -> bool
```

## Data Models

### Key Storage Model
```python
@dataclass
class StoredKey:
    key_id: str
    owner_id: str  # Coral wallet/session ID
    key_name: str
    encrypted_key: bytes
    created_at: datetime
    last_rotated: datetime
    is_active: bool
    coral_session_id: str
```

### Access Grant Model
```python
@dataclass
class AccessGrant:
    grant_id: str
    key_id: str
    caller_id: str  # Coral wallet/session ID
    permissions: dict  # {"max_calls_per_day": 100}
    created_at: datetime
    expires_at: datetime
    is_active: bool
    granted_by: str  # Owner's Coral ID
```

### Privacy-Conscious Audit Log Model
```python
@dataclass
class PrivacyAuditLog:
    log_id: str
    timestamp: datetime
    caller_id: str
    key_id: str
    action: str  # "proxy_call", "grant_access", etc.
    method: str  # HTTP method
    endpoint: str  # Target API endpoint
    payload_size: int  # Size in bytes, not content
    response_time: float  # Milliseconds
    response_code: int
    error_message: str = None
```

### Usage Counter Model
```python
@dataclass
class UsageCounter:
    key_id: str
    caller_id: str
    date: date
    call_count: int
    total_payload_size: int
    average_response_time: float
    last_reset: datetime
```


***Error Handling (MVP)***
****Error Categories****
1. Coral Authentication Errors: Invalid session/wallet ID, expired sessions

2. Authorization Errors: Insufficient permissions, expired grants

3. Rate Limit Errors: Usage quotas exceeded

4. Proxy Errors: External API failures, network issues

**Coral-Compatible Error Response**
```
@dataclass
class CoralErrorResponse:
    error_code: str
    error_message: str
    coral_session_id: str
    details: dict = None
    retry_after: int = None  # Only for rate limit errors
```

**Handling Strategy**

- Log errors minimally for debugging (metadata only)

- Return Coral-compatible error responses immediately

- No advanced retry/circuit breaker logic for MVP



## **Testing Strategy (MVP)**
#### **Unit Testing**

- Key Management: Store, rotate, revoke keys

- Authorization: Grant creation, validation, expiration

- Proxy Service: Forward requests and inject keys

- Policy Engine: Rate limits per caller per key

- Logging: Record minimal metadata



#### **Integration Testing**

- End-to-End Flow: Agent A stores key → Agent B gets grant → Agent B makes a proxied call

- Mock Coral Agent for simulating requests and session validation

- Verify grant expiration and rate-limiting works


Sample Test Scenario
python
```
# Mock Coral agent
class MockCoralAgent:
    async def make_sage_call(self, key_id: str, target_url: str, payload: dict):
        pass

# Scenarios
# 1. Agent A stores OpenAI key
# 2. Agent A grants access to Agent B
# 3. Agent B successfully proxies a call
# 4. Agent B hits rate limit
# 5. Agent A revokes access and Agent B is denied
```


## **Security Considerations (MVP)**
#### **Key Protection**

- Encryption at Rest: AES-256 for stored keys

- Access Control: Only key owners can manage or view grants

- Key Rotation: Optional for MVP, can be manual


#### **Network & Coral Integration**

- HTTPS for all external calls (proxy)

- Coral Session Validation for each request

- Minimal input validation to prevent malformed requests


#### **Privacy**

- Logging Metadata Only: No full payloads

- Only owners can query logs