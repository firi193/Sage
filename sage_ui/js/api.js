// API client for communicating with Sage backend

// Determine API base URL based on current location
const API_BASE = (() => {
    const hostname = window.location.hostname;
    const port = window.location.port;
    
    // Local development
    if (hostname === 'localhost' || hostname === '127.0.0.1') {
        if (port === '8080') {
            return 'http://localhost:8001/api/v1'; // Separate backend server
        }
        return '/api/v1'; // Same server (FastAPI serving static files)
    }
    
    // Production - same domain
    return '/api/v1';
})();

/**
 * Custom API Error class for better error handling
 */
class APIError extends Error {
    constructor(message, status = 500, details = {}) {
        super(message);
        this.name = 'APIError';
        this.status = status;
        this.details = details;
        this.userMessage = this.generateUserMessage(status, message);
    }
    
    /**
     * Generate user-friendly error messages based on status codes
     */
    generateUserMessage(status, message) {
        switch (status) {
            case 400:
                return 'Invalid request. Please check your input and try again.';
            case 401:
                return 'Authentication required. Please log in and try again.';
            case 403:
                return 'You do not have permission to perform this action.';
            case 404:
                return 'The requested resource was not found.';
            case 409:
                return 'This action conflicts with existing data. Please refresh and try again.';
            case 422:
                return message || 'Invalid data provided. Please check your input.';
            case 429:
                return 'Too many requests. Please wait a moment and try again.';
            case 500:
                return 'Server error. Please try again later.';
            case 503:
                return 'Service temporarily unavailable. Please try again later.';
            default:
                return message || 'An error occurred. Please try again.';
        }
    }
}

const API_ENDPOINTS = {
    // Keys - Maps to existing SageMCP.add_key() and KeyManager methods
    listKeys: () => `${API_BASE}/keys`,
    addKey: () => `${API_BASE}/keys`,
    deleteKey: (keyId) => `${API_BASE}/keys/${keyId}`,
    
    // Grants - Maps to existing SageMCP.grant_access() and AuthorizationEngine methods
    listGrants: (keyId = null) => keyId ? `${API_BASE}/grants?key_id=${keyId}` : `${API_BASE}/grants`,
    createGrant: () => `${API_BASE}/grants`,
    revokeGrant: (grantId) => `${API_BASE}/grants/${grantId}`,
    
    // Logs - Maps to existing SageMCP.list_logs() method
    getLogs: (keyId = null, timeFilter = '24h') => {
        const params = new URLSearchParams();
        if (keyId) params.append('key_id', keyId);
        params.append('time_filter', timeFilter);
        return `${API_BASE}/logs?${params}`;
    }
};

/**
 * Main API client class with comprehensive error handling and loading state management
 */
class SageAPI {
    constructor() {
        this.baseURL = API_BASE;
        this.requestTimeout = 30000; // 30 seconds
        this.activeRequests = new Map(); // Track active requests for loading states
    }
    
    /**
     * Make HTTP request with comprehensive error handling and loading state management
     */
    async request(endpoint, options = {}) {
        const requestId = this.generateRequestId();
        const loadingElement = options.loadingElement;
        
        try {
            // Set loading state
            this.setRequestLoading(requestId, loadingElement, true);
            
            // Create abort controller for timeout
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), this.requestTimeout);
            
            const requestOptions = {
                headers: {
                    'Content-Type': 'application/json',
                    ...options.headers
                },
                signal: controller.signal,
                ...options
            };
            
            const response = await fetch(endpoint, requestOptions);
            clearTimeout(timeoutId);
            
            if (!response.ok) {
                const errorData = await this.parseErrorResponse(response);
                throw new APIError(
                    errorData.message || `Request failed with status ${response.status}`,
                    response.status,
                    errorData
                );
            }
            
            const data = await this.parseSuccessResponse(response);
            return data;
            
        } catch (error) {
            this.handleRequestError(error, endpoint);
            throw error;
        } finally {
            // Clear loading state
            this.setRequestLoading(requestId, loadingElement, false);
        }
    }
    
    /**
     * Generate unique request ID for tracking
     */
    generateRequestId() {
        return 'req-' + Date.now() + '-' + Math.random().toString(36).substring(2, 9);
    }
    
    /**
     * Set loading state for request
     */
    setRequestLoading(requestId, element, isLoading) {
        if (isLoading) {
            this.activeRequests.set(requestId, { element, startTime: Date.now() });
            if (element) {
                this.showLoadingState(element);
            }
            // Emit loading event for global loading indicators
            window.appEvents?.emit('api:loading:start', { requestId, element });
        } else {
            const request = this.activeRequests.get(requestId);
            if (request) {
                if (request.element) {
                    this.hideLoadingState(request.element);
                }
                this.activeRequests.delete(requestId);
            }
            // Emit loading complete event
            window.appEvents?.emit('api:loading:end', { requestId, element });
        }
    }
    
    /**
     * Show loading state on element
     */
    showLoadingState(element) {
        if (!element) return;
        element.classList.add('loading');
        element.style.pointerEvents = 'none';
        
        // Add loading spinner if not present
        if (!element.querySelector('.loading-spinner')) {
            const spinner = document.createElement('div');
            spinner.className = 'loading-spinner';
            spinner.innerHTML = '<div class="spinner"></div>';
            element.appendChild(spinner);
        }
    }
    
    /**
     * Hide loading state on element
     */
    hideLoadingState(element) {
        if (!element) return;
        element.classList.remove('loading');
        element.style.pointerEvents = '';
        
        // Remove loading spinner
        const spinner = element.querySelector('.loading-spinner');
        if (spinner) {
            spinner.remove();
        }
    }
    
    /**
     * Parse error response with detailed error information
     */
    async parseErrorResponse(response) {
        try {
            const contentType = response.headers.get('content-type');
            if (contentType && contentType.includes('application/json')) {
                return await response.json();
            } else {
                const text = await response.text();
                return { message: text || response.statusText };
            }
        } catch (parseError) {
            return { 
                message: `Failed to parse error response: ${response.statusText}`,
                parseError: parseError.message 
            };
        }
    }
    
    /**
     * Parse success response
     */
    async parseSuccessResponse(response) {
        try {
            const contentType = response.headers.get('content-type');
            if (contentType && contentType.includes('application/json')) {
                return await response.json();
            } else {
                return await response.text();
            }
        } catch (parseError) {
            throw new APIError('Failed to parse response data', 500, { parseError: parseError.message });
        }
    }
    
    /**
     * Handle request errors with detailed logging and user feedback
     */
    handleRequestError(error, endpoint) {
        const errorInfo = {
            endpoint,
            timestamp: new Date().toISOString(),
            error: error.message,
            type: error.name
        };
        
        // Log error details
        console.error('API Request Error:', errorInfo);
        
        // Emit error event for global error handling
        window.appEvents?.emit('api:error', errorInfo);
        
        // Show user-friendly error message
        if (error.name === 'AbortError') {
            this.showErrorNotification('Request timed out. Please try again.');
        } else if (error instanceof APIError) {
            this.showErrorNotification(error.userMessage || error.message);
        } else if (error.name === 'TypeError' && error.message.includes('fetch')) {
            this.showErrorNotification('Network error. Please check your connection and try again.');
        } else {
            this.showErrorNotification('An unexpected error occurred. Please try again.');
        }
    }
    
    /**
     * Show error notification to user
     */
    showErrorNotification(message) {
        if (window.notificationManager) {
            window.notificationManager.showError(message);
        } else {
            // Fallback to console if notification manager not available
            console.error('Error notification:', message);
        }
    }
    
    /**
     * Show success notification to user
     */
    showSuccessNotification(message) {
        if (window.notificationManager) {
            window.notificationManager.showSuccess(message);
        }
    }
    
    /**
     * Check if there are any active requests
     */
    hasActiveRequests() {
        return this.activeRequests.size > 0;
    }
    
    /**
     * Get count of active requests
     */
    getActiveRequestCount() {
        return this.activeRequests.size;
    }
    
    /**
     * Cancel all active requests
     */
    cancelAllRequests() {
        this.activeRequests.forEach((request, requestId) => {
            if (request.element) {
                this.hideLoadingState(request.element);
            }
        });
        this.activeRequests.clear();
    }
    
    // Key operations
    async listKeys(loadingElement = null) {
        try {
            const keys = await this.request(API_ENDPOINTS.listKeys(), { loadingElement });
            return this.processKeysResponse(keys);
        } catch (error) {
            throw new APIError('Failed to load API keys', error.status, { originalError: error });
        }
    }
    
    async addKey(keyData, loadingElement = null) {
        try {
            // Validate key data before sending
            this.validateKeyData(keyData);
            
            const result = await this.request(API_ENDPOINTS.addKey(), {
                method: 'POST',
                body: JSON.stringify(keyData),
                loadingElement
            });
            
            this.showSuccessNotification('API key added successfully');
            return result;
        } catch (error) {
            if (error instanceof APIError) throw error;
            throw new APIError('Failed to add API key', error.status, { originalError: error });
        }
    }
    
    async deleteKey(keyId, loadingElement = null) {
        try {
            if (!keyId) {
                throw new APIError('Key ID is required', 400);
            }
            
            const result = await this.request(API_ENDPOINTS.deleteKey(keyId), {
                method: 'DELETE',
                loadingElement
            });
            
            this.showSuccessNotification('API key deleted successfully');
            return result;
        } catch (error) {
            if (error instanceof APIError) throw error;
            throw new APIError('Failed to delete API key', error.status, { originalError: error });
        }
    }
    
    // Grant operations
    async listGrants(keyId = null, loadingElement = null) {
        try {
            const grants = await this.request(API_ENDPOINTS.listGrants(keyId), { loadingElement });
            return this.processGrantsResponse(grants);
        } catch (error) {
            throw new APIError('Failed to load access grants', error.status, { originalError: error });
        }
    }
    
    async createGrant(grantData, loadingElement = null) {
        try {
            // Validate grant data before sending
            this.validateGrantData(grantData);
            
            const result = await this.request(API_ENDPOINTS.createGrant(), {
                method: 'POST',
                body: JSON.stringify(grantData),
                loadingElement
            });
            
            this.showSuccessNotification('Access grant created successfully');
            return result;
        } catch (error) {
            if (error instanceof APIError) throw error;
            throw new APIError('Failed to create access grant', error.status, { originalError: error });
        }
    }
    
    async revokeGrant(grantId, loadingElement = null) {
        try {
            if (!grantId) {
                throw new APIError('Grant ID is required', 400);
            }
            
            const result = await this.request(API_ENDPOINTS.revokeGrant(grantId), {
                method: 'DELETE',
                loadingElement
            });
            
            this.showSuccessNotification('Access grant revoked successfully');
            return result;
        } catch (error) {
            if (error instanceof APIError) throw error;
            throw new APIError('Failed to revoke access grant', error.status, { originalError: error });
        }
    }
    
    // Log operations
    async getLogs(keyId = null, timeFilter = '24h', loadingElement = null) {
        try {
            // For now, return mock data since backend endpoints aren't implemented yet
            // This will be replaced with actual API call in task 8
            const mockLogs = this.generateMockLogs(keyId, timeFilter);
            
            // Simulate API delay
            await new Promise(resolve => setTimeout(resolve, 500));
            
            return this.processLogsResponse(mockLogs);
            
            // TODO: Replace with actual API call when backend is implemented
            // const logs = await this.request(API_ENDPOINTS.getLogs(keyId, timeFilter), { loadingElement });
            // return this.processLogsResponse(logs);
        } catch (error) {
            throw new APIError('Failed to load usage logs', error.status, { originalError: error });
        }
    }
    
    /**
     * Generate mock logs data for testing (temporary)
     */
    generateMockLogs(keyId = null, timeFilter = '24h') {
        const mockLogs = [];
        const now = new Date();
        const timeRange = timeFilter === '24h' ? 24 * 60 * 60 * 1000 : 7 * 24 * 60 * 60 * 1000;
        
        // Generate 10-20 mock log entries
        const logCount = Math.floor(Math.random() * 11) + 10;
        
        const mockCallerIds = ['agent-001', 'app-dashboard', 'mobile-app', 'web-client', 'batch-processor'];
        const mockEndpoints = [
            '/api/v1/chat/completions',
            '/api/v1/embeddings',
            '/api/v1/models',
            '/api/v1/completions',
            '/api/v1/images/generations'
        ];
        const mockStatuses = [200, 200, 200, 201, 400, 401, 429, 500];
        
        // Get available keys for mock data
        const availableKeys = window.keysManager?.keys || [];
        const mockKeys = availableKeys.length > 0 ? availableKeys : [
            { key_id: 'key-1', key_name: 'OpenAI Production', environment: 'prod' },
            { key_id: 'key-2', key_name: 'OpenAI Staging', environment: 'staging' }
        ];
        
        for (let i = 0; i < logCount; i++) {
            const randomTime = new Date(now.getTime() - Math.random() * timeRange);
            const randomKey = mockKeys[Math.floor(Math.random() * mockKeys.length)];
            const randomStatus = mockStatuses[Math.floor(Math.random() * mockStatuses.length)];
            const randomResponseTime = Math.floor(Math.random() * 2000) + 50;
            
            // Skip this log if we're filtering by key and it doesn't match
            if (keyId && randomKey.key_id !== keyId) {
                continue;
            }
            
            mockLogs.push({
                id: `log-${i}-${Date.now()}`,
                timestamp: randomTime.toISOString(),
                caller_id: mockCallerIds[Math.floor(Math.random() * mockCallerIds.length)],
                key_id: randomKey.key_id,
                key_name: randomKey.key_name,
                endpoint: mockEndpoints[Math.floor(Math.random() * mockEndpoints.length)],
                response_code: randomStatus,
                response_time: randomResponseTime,
                method: 'POST'
            });
        }
        
        // Sort by timestamp (newest first)
        mockLogs.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
        
        return mockLogs;
    }
    
    // Data validation methods
    validateKeyData(keyData) {
        const errors = [];
        
        if (!keyData.key_name || !keyData.key_name.trim()) {
            errors.push('Key name is required');
        }
        
        if (!keyData.environment) {
            errors.push('Environment is required');
        } else if (!['staging', 'prod'].includes(keyData.environment)) {
            errors.push('Environment must be either "staging" or "prod"');
        }
        
        if (!keyData.api_key || !keyData.api_key.trim()) {
            errors.push('API key is required');
        }
        
        if (errors.length > 0) {
            throw new APIError(errors.join(', '), 422, { validationErrors: errors });
        }
    }
    
    validateGrantData(grantData) {
        const errors = [];
        
        if (!grantData.key_id) {
            errors.push('Key selection is required');
        }
        
        if (!grantData.caller_agent_id || !grantData.caller_agent_id.trim()) {
            errors.push('Agent/App ID is required');
        } else if (!/^[a-zA-Z0-9_-]+$/.test(grantData.caller_agent_id)) {
            errors.push('Agent/App ID can only contain letters, numbers, underscores, and hyphens');
        }
        
        if (!grantData.max_calls_per_day || grantData.max_calls_per_day < 1) {
            errors.push('Max calls per day must be at least 1');
        }
        
        if (!grantData.expiry_date) {
            errors.push('Expiry date is required');
        } else if (new Date(grantData.expiry_date) <= new Date()) {
            errors.push('Expiry date must be in the future');
        }
        
        if (errors.length > 0) {
            throw new APIError(errors.join(', '), 422, { validationErrors: errors });
        }
    }
    
    // Response processing methods
    processKeysResponse(keys) {
        if (!Array.isArray(keys)) {
            return [];
        }
        
        return keys.map(key => ({
            ...key,
            created_at: key.created_at ? new Date(key.created_at) : null,
            is_active: Boolean(key.is_active),
            grant_count: key.grant_count || 0
        }));
    }
    
    processGrantsResponse(grants) {
        if (!Array.isArray(grants)) {
            return [];
        }
        
        return grants.map(grant => ({
            ...grant,
            expires_at: grant.expires_at ? new Date(grant.expires_at) : null,
            created_at: grant.created_at ? new Date(grant.created_at) : null,
            is_active: Boolean(grant.is_active),
            current_usage: grant.current_usage || 0
        }));
    }
    
    processLogsResponse(logs) {
        if (!Array.isArray(logs)) {
            return [];
        }
        
        return logs.map(log => ({
            ...log,
            timestamp: log.timestamp ? new Date(log.timestamp) : null,
            response_time: log.response_time || 0
        }));
    }
}

// Global API client instance
window.sageAPI = new SageAPI();