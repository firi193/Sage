# Requirements Document

## Introduction

The Sage UI MVP is a simple web-based interface that provides basic functionality for managing API keys and access grants through the Sage system. This MVP focuses on core features needed to interact with the Sage backend without requiring command-line knowledge.

## Requirements

### Requirement 1

**User Story:** As a user (agent owner or app builder), I want a simple dashboard to view and add my API keys, so that I can manage my keys through a web interface.

#### Acceptance Criteria

1. WHEN accessing the dashboard THEN the UI SHALL display a list of my API keys with key_name, environment, and status
2. WHEN adding a new key THEN the UI SHALL provide a simple form with key_name, api_key, and environment dropdown (staging/prod) fields
3. WHEN a key is added THEN the UI SHALL show success confirmation and refresh the key list
4. WHEN viewing keys THEN the UI SHALL never display the actual API key values
5. WHEN deleting a key THEN the UI SHALL show a confirmation dialog before removal

### Requirement 2

**User Story:** As a user (agent owner or app builder), I want to create and view access grants for my keys, so that I can allow other agents to use my API keys.

#### Acceptance Criteria

1. WHEN clicking on a key THEN the UI SHALL show existing grants for that key
2. WHEN creating a grant THEN the UI SHALL provide a form with caller_agent_id, max_calls_per_day, and expiry_date
3. WHEN a grant is created THEN the UI SHALL show success confirmation and update the grants list
4. WHEN viewing grants THEN the UI SHALL show caller_id, daily limit, expiry date, and status
5. WHEN revoking a grant THEN the UI SHALL provide a simple revoke button with confirmation

### Requirement 3

**User Story:** As a user (agent owner or app builder), I want to see basic usage logs for my keys, so that I can monitor how they are being used.

#### Acceptance Criteria

1. WHEN viewing a key THEN the UI SHALL show recent API calls made through that key
2. WHEN displaying logs THEN the UI SHALL show timestamp, caller_id, endpoint, and response_status
3. WHEN filtering logs THEN the UI SHALL provide a simple dropdown with "Last 24h" and "Last 7d" options
4. WHEN viewing logs THEN the UI SHALL limit display to the most recent 50 calls for the selected time period
5. WHEN no logs exist THEN the UI SHALL display a "No usage yet" message
6. WHEN logs are loading THEN the UI SHALL show a simple loading indicator

### Requirement 4

**User Story:** As a user, I want a simple and clean interface that works on desktop browsers, so that I can easily navigate and use the Sage system.

#### Acceptance Criteria

1. WHEN accessing the UI THEN it SHALL work properly on desktop browsers (Chrome, Firefox, Safari)
2. WHEN navigating THEN the UI SHALL have a simple menu with "Keys", "Grants", and "Logs" sections
3. WHEN designing the layout THEN the UI SHALL reserve space for future analytics and alerts features without requiring redesign
4. WHEN forms have errors THEN the UI SHALL display clear error messages
5. WHEN actions succeed THEN the UI SHALL show brief success notifications
6. WHEN data is loading THEN the UI SHALL show loading states to indicate progress