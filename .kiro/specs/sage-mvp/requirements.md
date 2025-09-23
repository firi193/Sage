# Requirements Document

## Introduction

Sage is a Coral Agent that provides secure API key usage, proxying, and traceability for other agents on the Internet of Agents (IoA). The system eliminates the need for agents to share API keys directly while providing comprehensive tracking, access control, and policy enforcement. Sage acts as a secure intermediary that stores API keys once and issues scoped, short-lived access tokens to authorized agents, ensuring zero key sharing while maintaining full traceability of all API calls.

## Requirements

### Requirement 1

**User Story:** As an agent owner, I want to securely store my API keys in Sage, so that I never have to share them directly with other agents while still allowing controlled access to my services.

#### Acceptance Criteria

1. WHEN an agent owner submits an API key THEN Sage SHALL encrypt and store the key securely at rest
2. WHEN storing a key THEN Sage SHALL never store the key in plaintext format
3. WHEN a key is stored THEN Sage SHALL assign a unique key_id for reference
4. WHEN listing keys THEN Sage SHALL return key metadata without exposing the actual key values
5. WHEN rotating a key THEN Sage SHALL update the stored key while maintaining the same key_id
6. WHEN revoking a key THEN Sage SHALL immediately invalidate all associated access grants

### Requirement 2

**User Story:** As an agent owner, I want to grant specific access permissions to other agents, so that I can control who can use my API keys and under what conditions.

#### Acceptance Criteria

1. WHEN granting access THEN Sage SHALL require key_id, caller_agent_id, permissions, and expiry parameters
2. WHEN creating a grant THEN Sage SHALL validate that the key_id exists and the granter owns it
3. WHEN setting permissions THEN Sage SHALL support rate limiting parameters (max_calls_per_day)
4. WHEN setting expiry THEN Sage SHALL automatically revoke access after the specified time
5. WHEN revoking access THEN Sage SHALL immediately block future calls from the specified caller
6. WHEN checking authorization THEN Sage SHALL verify both grant validity and policy compliance

### Requirement 3

**User Story:** As a calling agent, I want to make API calls through Sage using a key_id, so that I can access services without ever seeing the actual API keys.

#### Acceptance Criteria

1. WHEN making a proxy call THEN Sage SHALL require key_id, target_url, payload, and caller_agent_id
2. WHEN processing a call THEN Sage SHALL verify the caller is authorized for the specified key
3. WHEN forwarding requests THEN Sage SHALL inject the actual API key at runtime
4. WHEN receiving responses THEN Sage SHALL return the API response without exposing key details
5. IF authorization fails THEN Sage SHALL return an error without making the external call
6. IF rate limits are exceeded THEN Sage SHALL block the call and return a rate limit error

### Requirement 4

**User Story:** As an agent owner, I want comprehensive logging of all API calls made through my keys, so that I can track usage, debug issues, and maintain security oversight.

#### Acceptance Criteria

1. WHEN any proxy call is made THEN Sage SHALL log caller_agent_id, key_id, timestamp, request_metadata(method, endpoint, payload size (not full payload for privacy), response time), and status_code
2. WHEN logging calls THEN Sage SHALL ensure logs are tamper-resistant and chronologically ordered
3. WHEN retrieving logs THEN Sage SHALL provide filtering by key_id, caller_agent_id, and time range
4. WHEN accessing logs THEN Sage SHALL only allow key owners to view logs for their keys
5. WHEN calls fail THEN Sage SHALL log error details and failure reasons
6. WHEN rate limits are hit THEN Sage SHALL log the blocked attempt with relevant context

### Requirement 5

**User Story:** As an agent owner, I want automatic policy enforcement on my API keys, so that I can prevent abuse and control costs without manual intervention.

#### Acceptance Criteria

1. WHEN setting rate limits THEN Sage SHALL enforce max_calls_per_day per caller per key
2. WHEN rate limits are exceeded THEN Sage SHALL immediately block subsequent calls
3. WHEN policies are updated THEN Sage SHALL apply changes to future calls immediately
4. WHEN grants expire THEN Sage SHALL automatically revoke access without manual intervention
5. IF a key is revoked THEN Sage SHALL immediately block all calls using that key
6. WHEN checking policies THEN Sage SHALL validate all active constraints before proxying calls

### Requirement 6

User Story: As an agent owner or calling agent, I want Sage to expose a Coral-compatible interface so that agents can interact with it securely, reliably, and according to the protocol.

Acceptance Criteria

1. WHEN exposing the interface THEN Sage SHALL implement Coral’s MCP protocol for all agent communications
2. WHEN authenticating callers THEN Sage SHALL rely on Coral session IDs or wallet IDs for caller identity
3. WHEN handling requests THEN Sage SHALL validate all input parameters according to MCP specifications
4. WHEN returning responses THEN Sage SHALL follow MCP protocol formats and standards
5. IF authentication or session validation fails THEN Sage SHALL reject requests with proper error codes
6. WHEN processing concurrent requests THEN Sage SHALL maintain consistency, security, and correct request ordering