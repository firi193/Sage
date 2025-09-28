// Utility functions for the Sage UI

/**
 * Format date for display
 */
function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
}

/**
 * Format relative time (e.g., "2 hours ago")
 */
function formatRelativeTime(dateString) {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMins / 60);
    const diffDays = Math.floor(diffHours / 24);
    
    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins} min ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    
    return formatDate(dateString);
}

/**
 * Sanitize input to prevent XSS
 */
function sanitizeInput(input) {
    if (typeof input !== 'string') return input;
    return input.replace(/[<>\"']/g, '');
}

/**
 * Validate agent/app ID format
 */
function validateAgentId(agentId) {
    return /^[a-zA-Z0-9_-]+$/.test(agentId);
}

/**
 * Generate a simple UUID for client-side use
 */
function generateId() {
    return 'id-' + Math.random().toString(36).substring(2, 11);
}

/**
 * Debounce function to limit rapid function calls
 */
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

/**
 * Show/hide loading state on an element
 */
function setLoadingState(element, isLoading) {
    if (isLoading) {
        element.classList.add('loading');
        element.style.pointerEvents = 'none';
    } else {
        element.classList.remove('loading');
        element.style.pointerEvents = '';
    }
}

/**
 * Create a loading spinner element
 */
function createLoadingSpinner() {
    const spinner = document.createElement('div');
    spinner.className = 'loading-spinner';
    return spinner;
}

/**
 * Escape HTML to prevent XSS
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Simple event emitter for component communication
 */
class EventEmitter {
    constructor() {
        this.events = {};
    }
    
    on(event, callback) {
        if (!this.events[event]) {
            this.events[event] = [];
        }
        this.events[event].push(callback);
    }
    
    emit(event, data) {
        if (this.events[event]) {
            this.events[event].forEach(callback => callback(data));
        }
    }
    
    off(event, callback) {
        if (this.events[event]) {
            this.events[event] = this.events[event].filter(cb => cb !== callback);
        }
    }
}

/**
 * Notification manager for user feedback
 */
class NotificationManager {
    constructor() {
        this.container = this.createContainer();
        this.notifications = new Map();
    }
    
    createContainer() {
        let container = document.querySelector('.notifications');
        if (!container) {
            container = document.createElement('div');
            container.className = 'notifications';
            document.body.appendChild(container);
        }
        return container;
    }
    
    show(message, type = 'info', duration = 5000) {
        const id = this.generateId();
        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        notification.innerHTML = `
            <span class="notification-message">${this.escapeHtml(message)}</span>
            <button class="notification-close" onclick="window.notificationManager.remove('${id}')">×</button>
        `;
        
        this.container.appendChild(notification);
        this.notifications.set(id, notification);
        
        // Auto-remove after duration
        if (duration > 0) {
            setTimeout(() => this.remove(id), duration);
        }
        
        return id;
    }
    
    showError(message, duration = 7000) {
        return this.show(message, 'error', duration);
    }
    
    showSuccess(message, duration = 3000) {
        return this.show(message, 'success', duration);
    }
    
    showWarning(message, duration = 5000) {
        return this.show(message, 'warning', duration);
    }
    
    showInfo(message, duration = 5000) {
        return this.show(message, 'info', duration);
    }
    
    remove(id) {
        const notification = this.notifications.get(id);
        if (notification) {
            notification.remove();
            this.notifications.delete(id);
        }
    }
    
    clear() {
        this.notifications.forEach((notification, id) => {
            notification.remove();
        });
        this.notifications.clear();
    }
    
    generateId() {
        return 'notification-' + Date.now() + '-' + Math.random().toString(36).substring(2, 9);
    }
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

/**
 * Request/Response processing utilities
 */
class RequestUtils {
    /**
     * Build query string from object
     */
    static buildQueryString(params) {
        const searchParams = new URLSearchParams();
        Object.entries(params).forEach(([key, value]) => {
            if (value !== null && value !== undefined && value !== '') {
                searchParams.append(key, value);
            }
        });
        return searchParams.toString();
    }
    
    /**
     * Parse response headers into object
     */
    static parseHeaders(headers) {
        const headerObj = {};
        for (const [key, value] of headers.entries()) {
            headerObj[key] = value;
        }
        return headerObj;
    }
    
    /**
     * Format request data for logging
     */
    static formatRequestLog(method, url, data = null) {
        return {
            method: method.toUpperCase(),
            url,
            timestamp: new Date().toISOString(),
            data: data ? (typeof data === 'string' ? data : JSON.stringify(data)) : null
        };
    }
    
    /**
     * Format response data for logging
     */
    static formatResponseLog(status, data = null, duration = 0) {
        return {
            status,
            timestamp: new Date().toISOString(),
            duration: `${duration}ms`,
            data: data ? (typeof data === 'string' ? data : JSON.stringify(data)) : null
        };
    }
    
    /**
     * Validate required fields in data object
     */
    static validateRequiredFields(data, requiredFields) {
        const missing = [];
        requiredFields.forEach(field => {
            if (!data[field] || (typeof data[field] === 'string' && !data[field].trim())) {
                missing.push(field);
            }
        });
        return missing;
    }
    
    /**
     * Sanitize data object for API requests
     */
    static sanitizeRequestData(data) {
        const sanitized = {};
        Object.entries(data).forEach(([key, value]) => {
            if (typeof value === 'string') {
                sanitized[key] = value.trim();
            } else {
                sanitized[key] = value;
            }
        });
        return sanitized;
    }
    
    /**
     * Check if response indicates success
     */
    static isSuccessResponse(status) {
        return status >= 200 && status < 300;
    }
    
    /**
     * Get error message from response
     */
    static getErrorMessage(response, defaultMessage = 'An error occurred') {
        if (response.message) return response.message;
        if (response.error) return response.error;
        if (response.detail) return response.detail;
        return defaultMessage;
    }
}

/**
 * Loading state manager for global loading indicators
 */
class LoadingStateManager {
    constructor() {
        this.activeLoaders = new Set();
        this.globalLoadingElement = null;
    }
    
    /**
     * Set global loading element
     */
    setGlobalLoadingElement(element) {
        this.globalLoadingElement = element;
    }
    
    /**
     * Add loading state
     */
    addLoader(id) {
        this.activeLoaders.add(id);
        this.updateGlobalState();
    }
    
    /**
     * Remove loading state
     */
    removeLoader(id) {
        this.activeLoaders.delete(id);
        this.updateGlobalState();
    }
    
    /**
     * Check if any loaders are active
     */
    hasActiveLoaders() {
        return this.activeLoaders.size > 0;
    }
    
    /**
     * Update global loading state
     */
    updateGlobalState() {
        if (this.globalLoadingElement) {
            if (this.hasActiveLoaders()) {
                this.globalLoadingElement.classList.add('app-loading');
            } else {
                this.globalLoadingElement.classList.remove('app-loading');
            }
        }
        
        // Emit global loading state change
        window.appEvents?.emit('loading:state:change', {
            isLoading: this.hasActiveLoaders(),
            activeCount: this.activeLoaders.size
        });
    }
    
    /**
     * Clear all loaders
     */
    clearAll() {
        this.activeLoaders.clear();
        this.updateGlobalState();
    }
}

// Global instances
window.appEvents = new EventEmitter();
window.notificationManager = new NotificationManager();
window.loadingStateManager = new LoadingStateManager();
window.requestUtils = RequestUtils;