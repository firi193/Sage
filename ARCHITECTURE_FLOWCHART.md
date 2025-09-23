# Sage Architecture Flowchart

This document shows how all the entities and functions in the Sage system interact with each other.

## System Architecture Overview

```mermaid
graph TB
    %% External Entities
    CoralAgent[Coral Agent]
    APIProvider[API Provider<br/>OpenAI, Anthropic, etc.]
    
    %% Main Entry Points
    MCPInterface[MCP Interface<br/>sage_mcp.py]
    
    %% Core Services Layer
    subgraph "Core Services"
        KeyManager[Key Manager Service<br/>key_manager.py]
        ProxyService[Proxy Service<br/>proxy_service.py]
        AuthEngine[Authorization Engine<br/>authorization_engine.py]
        PolicyEngine[Policy Engine<br/>policy_engine.py]
        LoggingService[Logging Service<br/>logging_service.py]
    end
    
    %% Storage Layer
    subgraph "Storage Layer"
        KeyStorage[Key Storage Service<br/>key_storage.py]
        EncryptionManager[Encryption Manager<br/>encryption.py]
        SQLiteDB[(SQLite Database<br/>sage_keys.db)]
    end
    
    %% Data Models
    subgraph "Data Models"
        StoredKey[StoredKey Model<br/>stored_key.py]
        AccessGrant[AccessGrant Model<br/>access_grant.py]
        UsageCounter[UsageCounter Model<br/>usage_counter.py]
        AuditLog[PrivacyAuditLog Model<br/>privacy_audit_log.py]
    end
    
    %% Flow Connections
    CoralAgent -->|MCP Protocol| MCPInterface
    MCPInterface -->|Store/Retrieve Keys| KeyManager
    MCPInterface -->|Proxy API Calls| ProxyService
    
    KeyManager -->|Encrypt/Decrypt| EncryptionManager
    KeyManager -->|Store/Retrieve| KeyStorage
    KeyStorage -->|Persist Data| SQLiteDB
    KeyStorage -->|Uses Models| StoredKey
    
    ProxyService -->|Check Authorization| AuthEngine
    ProxyService -->|Apply Policies| PolicyEngine
    ProxyService -->|Log Activity| LoggingService
    ProxyService -->|Forward Requests| APIProvider
    
    AuthEngine -->|Check Grants| AccessGrant
    PolicyEngine -->|Track Usage| UsageCounter
    LoggingService -->|Create Audit Trail| AuditLog
    
    %% Data Flow for Key Storage
    EncryptionManager -.->|Encrypts| StoredKey
    StoredKey -.->|Stored in| SQLiteDB
```

## Detailed Component Interactions

### 1. Key Storage Flow

```mermaid
sequenceDiagram
    participant CA as Coral Agent
    participant MCP as MCP Interface
    participant KM as Key Manager
    participant EM as Encryption Manager
    participant KS as Key Storage
    participant DB as SQLite DB
    
    CA->>MCP: store_key(api_key, key_name)
    MCP->>KM: store_api_key(owner_id, key_name, api_key)
    KM->>EM: encrypt(api_key)
    EM-->>KM: encrypted_bytes
    KM->>KS: store_key(StoredKey)
    KS->>DB: INSERT INTO stored_keys
    DB-->>KS: success
    KS-->>KM: True
    KM-->>MCP: key_id
    MCP-->>CA: {"key_id": "uuid", "status": "stored"}
```

### 2. API Proxy Flow

```mermaid
sequenceDiagram
    participant CA as Coral Agent
    participant MCP as MCP Interface
    participant PS as Proxy Service
    participant AE as Auth Engine
    participant PE as Policy Engine
    participant KM as Key Manager
    participant API as API Provider
    participant LS as Logging Service
    
    CA->>MCP: proxy_request(key_id, request_data)
    MCP->>PS: handle_request(key_id, request_data)
    PS->>AE: check_authorization(key_id, owner_id)
    AE-->>PS: authorized
    PS->>PE: check_policies(key_id, request_data)
    PE-->>PS: allowed
    PS->>KM: get_decrypted_key(key_id)
    KM-->>PS: api_key
    PS->>API: HTTP Request with api_key
    API-->>PS: API Response
    PS->>LS: log_request(key_id, request, response)
    PS-->>MCP: response_data
    MCP-->>CA: API Response
```

### 3. Encryption/Decryption Flow

```mermaid
graph LR
    subgraph "Encryption Process"
        PlainKey[Plain API Key<br/>sk-1234...] 
        MasterKey[Master Key<br/>Password/Generated]
        DerivedKey[Derived Key<br/>PBKDF2 + SHA256]
        FernetKey[Fernet Key<br/>AES-256 + HMAC]
        EncryptedKey[Encrypted Key<br/>Bytes]
    end
    
    PlainKey -->|Input| FernetKey
    MasterKey -->|PBKDF2| DerivedKey
    DerivedKey -->|Base64 Encode| FernetKey
    FernetKey -->|AES-256 Encrypt| EncryptedKey
    
    subgraph "Decryption Process"
        EncryptedKey2[Encrypted Key<br/>Bytes]
        FernetKey2[Fernet Key<br/>AES-256 + HMAC]
        PlainKey2[Plain API Key<br/>sk-1234...]
    end
    
    EncryptedKey2 -->|AES-256 Decrypt| FernetKey2
    FernetKey2 -->|Output| PlainKey2
```

## Component Responsibilities

### Models Layer
- **StoredKey**: Represents encrypted API keys with metadata
- **AccessGrant**: Defines access permissions and scopes
- **UsageCounter**: Tracks API usage and rate limits
- **PrivacyAuditLog**: Records all access and operations for compliance

### Services Layer
- **KeyManager**: High-level key management operations
- **KeyStorage**: Low-level database operations for key persistence
- **ProxyService**: Handles API request proxying and response processing
- **AuthorizationEngine**: Validates access permissions
- **PolicyEngine**: Enforces usage policies and rate limits
- **LoggingService**: Creates audit trails and compliance logs

### Utils Layer
- **EncryptionManager**: Handles AES-256 encryption/decryption
- **Validation Functions**: API key format validation

### Interface Layer
- **MCP Interface**: Exposes functionality via Model Context Protocol
- **sage_mcp.py**: Main MCP server implementation

## Data Flow Summary

1. **Key Storage**: Coral Agent → MCP → KeyManager → EncryptionManager → KeyStorage → SQLite
2. **Key Retrieval**: SQLite → KeyStorage → KeyManager → EncryptionManager → MCP → Coral Agent
3. **API Proxying**: Coral Agent → MCP → ProxyService → (Auth/Policy checks) → API Provider → Response logging
4. **Audit Trail**: All operations → LoggingService → PrivacyAuditLog → SQLite

## Security Boundaries

```mermaid
graph TB
    subgraph "Trusted Zone"
        subgraph "Encrypted Storage"
            EncKeys[Encrypted API Keys]
            SQLiteDB2[(SQLite Database)]
        end
        
        subgraph "Memory (Temporary)"
            PlainKeys[Decrypted Keys<br/>Short-lived]
        end
    end
    
    subgraph "External Zone"
        CoralAgent2[Coral Agent]
        APIProviders[API Providers]
    end
    
    CoralAgent2 -.->|MCP Protocol| PlainKeys
    PlainKeys -.->|HTTPS| APIProviders
    PlainKeys -->|Encrypt| EncKeys
    EncKeys -->|Store| SQLiteDB2
```

The system maintains security by:
- Encrypting all API keys at rest using AES-256
- Keeping decrypted keys in memory only during active requests
- Using secure key derivation (PBKDF2) for master keys
- Implementing comprehensive audit logging
- Enforcing authorization and policy checks before key access