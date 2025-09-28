// UI component functions and utilities

// NotificationManager is now defined in utils.js

/**
 * Form Validator for client-side validation
 */
class FormValidator {
    validateKeyForm(formData) {
        const errors = [];

        if (!formData.key_name || !formData.key_name.trim()) {
            errors.push('Key name is required');
        }

        if (!formData.environment) {
            errors.push('Environment selection is required');
        }

        if (!formData.api_key || !formData.api_key.trim()) {
            errors.push('API key is required');
        }

        return errors;
    }

    validateGrantForm(formData) {
        const errors = [];

        if (!formData.key_id) {
            errors.push('Key selection is required');
        }

        if (!formData.caller_agent_id || !formData.caller_agent_id.trim()) {
            errors.push('Agent/App ID is required');
        } else if (!validateAgentId(formData.caller_agent_id)) {
            errors.push('Agent/App ID can only contain letters, numbers, hyphens, and underscores');
        }

        if (!formData.max_calls_per_day || formData.max_calls_per_day < 1) {
            errors.push('Max calls per day must be at least 1');
        }

        if (!formData.expiry_date) {
            errors.push('Expiry date is required');
        } else if (new Date(formData.expiry_date) <= new Date()) {
            errors.push('Expiry date must be in the future');
        }

        return errors;
    }

    displayErrors(form, errors) {
        // Clear existing errors
        form.querySelectorAll('.form-error').forEach(error => error.remove());
        form.querySelectorAll('.input-error').forEach(input => input.classList.remove('input-error'));

        if (errors.length === 0) return;

        // Show first error as general message
        const errorDiv = document.createElement('div');
        errorDiv.className = 'form-error';
        errorDiv.textContent = errors[0];
        form.insertBefore(errorDiv, form.firstChild);

        // Highlight problematic fields (basic implementation)
        errors.forEach(error => {
            if (error.includes('name')) {
                const nameInput = form.querySelector('[name="key_name"], [name="caller_agent_id"]');
                if (nameInput) nameInput.classList.add('input-error');
            }
            if (error.includes('environment') || error.includes('Key selection')) {
                const envSelect = form.querySelector('[name="environment"], [name="key_id"]');
                if (envSelect) envSelect.classList.add('input-error');
            }
            if (error.includes('API key')) {
                const keyInput = form.querySelector('[name="api_key"]');
                if (keyInput) keyInput.classList.add('input-error');
            }
            if (error.includes('calls')) {
                const callsInput = form.querySelector('[name="max_calls_per_day"]');
                if (callsInput) callsInput.classList.add('input-error');
            }
            if (error.includes('date')) {
                const dateInput = form.querySelector('[name="expiry_date"]');
                if (dateInput) dateInput.classList.add('input-error');
            }
        });
    }
}

/**
 * Modal Manager for handling modal dialogs
 */
class ModalManager {
    constructor() {
        this.activeModal = null;
        this.setupEventListeners();
    }

    setupEventListeners() {
        // Close modal when clicking outside
        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('modal')) {
                this.closeModal();
            }
        });

        // Close modal with Escape key
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.activeModal) {
                this.closeModal();
            }
        });
    }

    showModal(modalId) {
        console.log('showModal called with:', modalId);
        const modal = document.getElementById(modalId);
        if (modal) {
            console.log('Modal found, showing...');
            modal.classList.add('active');
            this.activeModal = modal;

            // Focus first input
            const firstInput = modal.querySelector('input, select, textarea');
            if (firstInput) {
                setTimeout(() => firstInput.focus(), 100);
            }
        } else {
            console.error('Modal not found:', modalId);
        }
    }

    closeModal() {
        console.log('closeModal called');
        if (this.activeModal) {
            console.log('Closing active modal:', this.activeModal.id);
            this.activeModal.classList.remove('active');
            this.activeModal = null;
        }

        // Close any modal that might be open
        document.querySelectorAll('.modal.active').forEach(modal => {
            console.log('Closing modal:', modal.id);
            modal.classList.remove('active');
        });
    }

    createModal(id, title, content) {
        const modal = document.createElement('div');
        modal.id = id;
        modal.className = 'modal';
        modal.innerHTML = `
            <div class="modal-content">
                <h3>${escapeHtml(title)}</h3>
                ${content}
            </div>
        `;

        document.body.appendChild(modal);
        return modal;
    }
}

/**
 * Session Manager for handling user session
 */
class SessionManager {
    constructor() {
        this.sessionKey = 'sage_session';
    }

    isSessionValid() {
        const sessionData = localStorage.getItem(this.sessionKey);
        if (!sessionData) return false;

        try {
            const session = JSON.parse(sessionData);
            return session.expires > Date.now();
        } catch {
            return false;
        }
    }

    setSession(data) {
        const session = {
            ...data,
            expires: Date.now() + (24 * 60 * 60 * 1000) // 24 hours
        };
        localStorage.setItem(this.sessionKey, JSON.stringify(session));
    }

    clearSession() {
        localStorage.removeItem(this.sessionKey);
    }

    getSession() {
        const sessionData = localStorage.getItem(this.sessionKey);
        if (!sessionData) return null;

        try {
            return JSON.parse(sessionData);
        } catch {
            return null;
        }
    }
}

// Global instances (NotificationManager is created in utils.js)
console.log('Creating global component instances...');
window.formValidator = new FormValidator();
window.modalManager = new ModalManager();
window.sessionManager = new SessionManager();

console.log('Global component instances created:', {
    notificationManager: !!window.notificationManager,
    formValidator: !!window.formValidator,
    modalManager: !!window.modalManager,
    sessionManager: !!window.sessionManager
});

/**
 * Key Management Functions
 */

/**
 * Key Model class for frontend data management
 */
class Key {
    constructor(data) {
        this.key_id = data.key_id;
        this.key_name = data.key_name;
        this.environment = data.environment;
        this.created_at = data.created_at ? new Date(data.created_at) : new Date();
        this.is_active = data.is_active !== undefined ? data.is_active : true;
        this.grant_count = data.grant_count || 0;
    }

    getDisplayName() {
        return `${this.key_name} (${this.environment})`;
    }

    getStatusBadge() {
        return this.is_active ? 'active' : 'inactive';
    }

    getFormattedDate() {
        return this.created_at.toLocaleDateString();
    }
}

/**
 * Keys Manager class for handling keys operations
 */
class KeysManager {
    constructor() {
        this.keys = [];
        this.keysListElement = document.getElementById('keys-list');
        this.placeholderElement = document.getElementById('keys-placeholder');
    }

    /**
     * Load and display keys
     */
    async loadKeys() {
        try {
            const keysData = await window.sageAPI.listKeys(this.keysListElement);
            this.keys = keysData.map(keyData => new Key(keyData));
            this.renderKeys();
            
            // If grants manager exists and has grants loaded, update grant counts
            if (window.grantsManager && window.grantsManager.grants.length > 0) {
                window.grantsManager.updateAllKeyGrantCounts();
            }
        } catch (error) {
            console.error('Failed to load keys:', error);
            this.showEmptyState('Failed to load API keys. Please try again.');
        }
    }

    /**
     * Render keys list
     */
    renderKeys() {
        if (this.keys.length === 0) {
            this.showEmptyState();
            return;
        }

        this.hideEmptyState();

        // Clear existing keys (except placeholder)
        const existingKeys = this.keysListElement.querySelectorAll('.key-item');
        existingKeys.forEach(item => item.remove());

        // Render each key
        this.keys.forEach(key => {
            const keyElement = this.createKeyElement(key);
            this.keysListElement.appendChild(keyElement);
        });
    }

    /**
     * Create HTML element for a key
     */
    createKeyElement(key) {
        const keyElement = document.createElement('div');
        keyElement.className = 'key-item';
        keyElement.setAttribute('data-key-id', key.key_id);

        keyElement.innerHTML = `
            <div class="item-header">
                <div class="item-title">${escapeHtml(key.key_name)}</div>
                <div class="item-actions">
                    <button class="btn-secondary" onclick="deleteKey('${key.key_id}', '${escapeHtml(key.key_name)}')">Delete</button>
                </div>
            </div>
            <div class="item-meta">
                <span>Environment: <strong>${key.environment}</strong></span>
                <span>Created: ${key.getFormattedDate()}</span>
                <span>Grants: ${key.grant_count}</span>
                <span class="status-badge status-${key.getStatusBadge()}">${key.getStatusBadge()}</span>
            </div>
        `;

        return keyElement;
    }

    /**
     * Show empty state
     */
    showEmptyState(message = 'Your API keys will appear here') {
        this.placeholderElement.style.display = 'block';
        this.placeholderElement.querySelector('p').textContent = message;
    }

    /**
     * Hide empty state
     */
    hideEmptyState() {
        this.placeholderElement.style.display = 'none';
    }

    /**
     * Add a new key
     */
    async addKey(keyData) {
        try {
            const result = await window.sageAPI.addKey(keyData, document.getElementById('add-key-form'));

            // Add the new key to our local list
            const newKey = new Key({
                key_id: result.key_id || Date.now().toString(), // Fallback ID
                ...keyData,
                created_at: new Date(),
                is_active: true,
                grant_count: 0
            });

            this.keys.push(newKey);
            this.renderKeys();

            // Update key filters for grants and logs managers
            if (window.grantsManager) {
                window.grantsManager.populateKeyFilter(this.keys);
            }
            
            if (window.logsManager) {
                window.logsManager.populateKeyFilter(this.keys);
            }

            // Close modal and reset form
            if (window.modalManager) {
                window.modalManager.closeModal();
            } else {
                // Fallback: close modal directly
                const modal = document.getElementById('add-key-modal');
                if (modal) {
                    modal.classList.remove('active');
                }
            }
            
            const form = document.getElementById('add-key-form');
            if (form) {
                form.reset();
            }

            return result;
        } catch (error) {
            console.error('Failed to add key:', error);
            throw error;
        }
    }

    /**
     * Delete a key
     */
    async deleteKey(keyId) {
        try {
            await window.sageAPI.deleteKey(keyId, document.getElementById('delete-key-modal'));

            // Remove key from local list
            this.keys = this.keys.filter(key => key.key_id !== keyId);
            this.renderKeys();

            // Update key filters for grants and logs managers
            if (window.grantsManager) {
                window.grantsManager.populateKeyFilter(this.keys);
            }
            
            if (window.logsManager) {
                window.logsManager.populateKeyFilter(this.keys);
            }

            // Close modal
            window.modalManager.closeModal();

        } catch (error) {
            console.error('Failed to delete key:', error);
            throw error;
        }
    }

    /**
     * Find key by ID
     */
    findKeyById(keyId) {
        return this.keys.find(key => key.key_id === keyId);
    }
}

// Global keys manager instance
window.keysManager = new KeysManager();

/**
 * Show Add Key Form Modal
 */
function showAddKeyForm() {
    console.log('showAddKeyForm called');
    if (window.modalManager) {
        window.modalManager.showModal('add-key-modal');
    } else {
        console.error('modalManager not available');
        // Fallback: show modal directly
        const modal = document.getElementById('add-key-modal');
        if (modal) {
            modal.classList.add('active');
        }
    }
}

// Ensure functions are available globally
window.showAddKeyForm = showAddKeyForm;

/**
 * Delete Key with confirmation
 */
function deleteKey(keyId, keyName) {
    const modal = document.getElementById('delete-key-modal');
    const keyInfo = document.getElementById('delete-key-info');
    const confirmButton = document.getElementById('confirm-delete-key');

    // Update modal content
    keyInfo.innerHTML = `
        <div class="key-info-item">
            <strong>Key Name:</strong> ${escapeHtml(keyName)}
        </div>
    `;

    // Set up confirm button
    confirmButton.onclick = async () => {
        try {
            confirmButton.classList.add('loading');
            await window.keysManager.deleteKey(keyId);
        } catch (error) {
            // Error is already handled by the API client
        } finally {
            confirmButton.classList.remove('loading');
        }
    };

    window.modalManager.showModal('delete-key-modal');
}

/**
 * Handle Add Key Form Submission
 */
async function handleAddKeyForm(formData, form) {
    try {
        // Validate form data
        const errors = window.formValidator.validateKeyForm(formData);
        if (errors.length > 0) {
            window.formValidator.displayErrors(form, errors);
            return;
        }

        // Clear any existing errors
        window.formValidator.displayErrors(form, []);

        // Add the key
        await window.keysManager.addKey(formData);

    } catch (error) {
        // Error is already handled by the API client and keysManager
        console.error('Add key form error:', error);
    }
}

// Placeholder functions for other features (will be implemented in later tasks)
function filterGrants() {
    window.notificationManager.showInfo('Grant filtering will be implemented in a future task');
}

function closeModal() {
    window.modalManager.closeModal();
}

/**
 * Grant Model class for frontend data management
 */
class Grant {
    constructor(data) {
        this.grant_id = data.grant_id;
        this.key_id = data.key_id;
        this.key_name = data.key_name;
        this.caller_id = data.caller_id;
        this.max_calls_per_day = data.max_calls_per_day;
        this.current_usage = data.current_usage || 0;
        this.expires_at = data.expires_at ? new Date(data.expires_at) : null;
        this.created_at = data.created_at ? new Date(data.created_at) : new Date();
        this.is_active = data.is_active !== undefined ? data.is_active : true;
    }

    getRemainingCalls() {
        return Math.max(0, this.max_calls_per_day - this.current_usage);
    }

    getUsagePercentage() {
        return Math.round((this.current_usage / this.max_calls_per_day) * 100);
    }

    isExpiringSoon() {
        if (!this.expires_at) return false;
        const oneDayFromNow = new Date(Date.now() + 24 * 60 * 60 * 1000);
        return this.expires_at <= oneDayFromNow;
    }

    isExpired() {
        if (!this.expires_at) return false;
        return this.expires_at <= new Date();
    }

    getStatusBadge() {
        if (!this.is_active) return 'inactive';
        if (this.isExpired()) return 'expired';
        if (this.isExpiringSoon()) return 'expiring';
        return 'active';
    }

    getFormattedExpiryDate() {
        return this.expires_at ? this.expires_at.toLocaleDateString() : 'Never';
    }

    getFormattedCreatedDate() {
        return this.created_at.toLocaleDateString();
    }
}

/**
 * Grants Manager class for handling grants operations
 */
class GrantsManager {
    constructor() {
        this.grants = [];
        this.grantsListElement = document.getElementById('grants-list');
        this.placeholderElement = document.getElementById('grants-placeholder');
        this.keyFilterElement = document.getElementById('key-filter');
        this.currentKeyFilter = '';
    }

    /**
     * Load and display grants
     */
    async loadGrants(keyId = null) {
        try {
            const grantsData = await window.sageAPI.listGrants(keyId, this.grantsListElement);
            this.grants = grantsData.map(grantData => new Grant(grantData));
            this.renderGrants();
            
            // Update key grant counts based on loaded grants
            this.updateAllKeyGrantCounts();
        } catch (error) {
            console.error('Failed to load grants:', error);
            this.showEmptyState('Failed to load access grants. Please try again.');
        }
    }

    /**
     * Render grants list
     */
    renderGrants() {
        const filteredGrants = this.getFilteredGrants();
        
        if (filteredGrants.length === 0) {
            this.showEmptyState(this.currentKeyFilter ? 
                'No grants found for the selected key' : 
                'No access grants created yet');
            return;
        }

        this.hideEmptyState();

        // Clear existing grants (except placeholder)
        const existingGrants = this.grantsListElement.querySelectorAll('.grant-item');
        existingGrants.forEach(item => item.remove());

        // Render each grant
        filteredGrants.forEach(grant => {
            const grantElement = this.createGrantElement(grant);
            this.grantsListElement.appendChild(grantElement);
        });
    }

    /**
     * Get filtered grants based on current key filter
     */
    getFilteredGrants() {
        if (!this.currentKeyFilter) {
            return this.grants;
        }
        return this.grants.filter(grant => grant.key_id === this.currentKeyFilter);
    }

    /**
     * Create HTML element for a grant
     */
    createGrantElement(grant) {
        const grantElement = document.createElement('div');
        grantElement.className = 'grant-item';
        grantElement.setAttribute('data-grant-id', grant.grant_id);

        const statusClass = grant.getStatusBadge();
        const usagePercentage = grant.getUsagePercentage();
        const remainingCalls = grant.getRemainingCalls();

        grantElement.innerHTML = `
            <div class="item-header">
                <div class="item-title">${escapeHtml(grant.caller_id)}</div>
                <div class="item-actions">
                    <button class="btn-secondary" onclick="revokeGrant('${grant.grant_id}', '${escapeHtml(grant.caller_id)}', '${escapeHtml(grant.key_name)}')">Revoke</button>
                </div>
            </div>
            <div class="item-meta">
                <span>Key: <strong>${escapeHtml(grant.key_name)}</strong></span>
                <span>Daily Limit: <strong>${grant.max_calls_per_day}</strong></span>
                <span>Used Today: <strong>${grant.current_usage} (${usagePercentage}%)</strong></span>
                <span>Remaining: <strong>${remainingCalls}</strong></span>
                <span>Expires: <strong>${grant.getFormattedExpiryDate()}</strong></span>
                <span class="status-badge status-${statusClass}">${statusClass}</span>
            </div>
        `;

        return grantElement;
    }

    /**
     * Show empty state
     */
    showEmptyState(message = 'Access grants will appear here') {
        if (this.placeholderElement) {
            this.placeholderElement.style.display = 'block';
            const p = this.placeholderElement.querySelector('p');
            if (p) {
                p.textContent = message;
            }
        }
    }

    /**
     * Hide empty state
     */
    hideEmptyState() {
        if (this.placeholderElement) {
            this.placeholderElement.style.display = 'none';
        }
    }

    /**
     * Create a new grant
     */
    async createGrant(grantData) {
        try {
            const result = await window.sageAPI.createGrant(grantData, document.getElementById('create-grant-form'));

            // Add the new grant to our local list
            const newGrant = new Grant({
                grant_id: result.grant_id || Date.now().toString(), // Fallback ID
                ...grantData,
                created_at: new Date(),
                is_active: true,
                current_usage: 0
            });

            this.grants.push(newGrant);
            this.renderGrants();

            // Update the grant count for the associated key
            this.updateKeyGrantCount(grantData.key_id, 1);

            // Close modal and reset form
            if (window.modalManager) {
                window.modalManager.closeModal();
            }
            
            const form = document.getElementById('create-grant-form');
            if (form) {
                form.reset();
            }

            return result;
        } catch (error) {
            console.error('Failed to create grant:', error);
            throw error;
        }
    }

    /**
     * Revoke a grant
     */
    async revokeGrant(grantId) {
        try {
            // Find the grant to get its key_id before revoking
            const grantToRevoke = this.grants.find(grant => grant.grant_id === grantId);
            
            await window.sageAPI.revokeGrant(grantId, document.getElementById('revoke-grant-modal'));

            // Remove grant from local list or mark as inactive
            this.grants = this.grants.map(grant => 
                grant.grant_id === grantId 
                    ? { ...grant, is_active: false }
                    : grant
            );
            this.renderGrants();

            // Update the grant count for the associated key (decrease by 1)
            if (grantToRevoke) {
                this.updateKeyGrantCount(grantToRevoke.key_id, -1);
            }

            // Close modal
            window.modalManager.closeModal();

        } catch (error) {
            console.error('Failed to revoke grant:', error);
            throw error;
        }
    }

    /**
     * Find grant by ID
     */
    findGrantById(grantId) {
        return this.grants.find(grant => grant.grant_id === grantId);
    }

    /**
     * Set key filter
     */
    setKeyFilter(keyId) {
        this.currentKeyFilter = keyId;
        this.renderGrants();
    }

    /**
     * Populate key filter dropdown with available keys
     */
    populateKeyFilter(keys) {
        if (!this.keyFilterElement) return;

        // Clear existing options except the first one
        while (this.keyFilterElement.children.length > 1) {
            this.keyFilterElement.removeChild(this.keyFilterElement.lastChild);
        }

        // Add keys as options
        keys.forEach(key => {
            const option = document.createElement('option');
            option.value = key.key_id;
            option.textContent = key.getDisplayName();
            this.keyFilterElement.appendChild(option);
        });
    }

    /**
     * Update grant count for a specific key
     */
    updateKeyGrantCount(keyId, increment) {
        if (window.keysManager && window.keysManager.keys) {
            const key = window.keysManager.keys.find(k => k.key_id === keyId);
            if (key) {
                key.grant_count = Math.max(0, key.grant_count + increment);
                // Re-render the keys list to show updated count
                window.keysManager.renderKeys();
            }
        }
    }

    /**
     * Update grant counts for all keys based on current grants
     */
    updateAllKeyGrantCounts() {
        if (window.keysManager && window.keysManager.keys) {
            // Reset all grant counts to 0
            window.keysManager.keys.forEach(key => {
                key.grant_count = 0;
            });

            // Count active grants for each key
            this.grants.forEach(grant => {
                if (grant.is_active) {
                    const key = window.keysManager.keys.find(k => k.key_id === grant.key_id);
                    if (key) {
                        key.grant_count++;
                    }
                }
            });

            // Re-render the keys list to show updated counts
            window.keysManager.renderKeys();
        }
    }
}

// Global grants manager instance - will be created when DOM is ready
window.grantsManager = null;

/**
 * Show Create Grant Form Modal
 */
function showCreateGrantForm() {
    console.log('showCreateGrantForm called');
    
    // First, ensure we have keys loaded
    if (!window.keysManager || !window.keysManager.keys || window.keysManager.keys.length === 0) {
        console.log('No keys available, loading keys first...');
        // Try to load keys first
        if (window.keysManager && window.keysManager.loadKeys) {
            window.keysManager.loadKeys().then(() => {
                populateKeyDropdown();
                showModal();
            }).catch(() => {
                // If loading fails, show modal anyway but with a message
                window.notificationManager.showWarning('No API keys found. Please add a key first.');
                showModal();
            });
        } else {
            // No keys manager, show modal anyway
            showModal();
        }
    } else {
        // Keys are already available
        populateKeyDropdown();
        showModal();
    }
    
    function populateKeyDropdown() {
        // Populate key dropdown with available keys
        const keySelect = document.querySelector('#create-grant-form select[name="key_id"]');
        if (keySelect && window.keysManager && window.keysManager.keys) {
            console.log('Populating key dropdown with', window.keysManager.keys.length, 'keys');
            
            // Clear existing options except the first one
            while (keySelect.children.length > 1) {
                keySelect.removeChild(keySelect.lastChild);
            }

            // Add keys as options
            window.keysManager.keys.forEach(key => {
                const option = document.createElement('option');
                option.value = key.key_id;
                option.textContent = key.getDisplayName();
                keySelect.appendChild(option);
            });
            
            // If no keys available, show a message
            if (window.keysManager.keys.length === 0) {
                const option = document.createElement('option');
                option.value = '';
                option.textContent = 'No API keys available - please add a key first';
                option.disabled = true;
                keySelect.appendChild(option);
            }
        } else {
            console.log('KeysManager or keys not available');
        }
    }
    
    function showModal() {
        // Set minimum date to tomorrow
        const dateInput = document.querySelector('#create-grant-form input[name="expiry_date"]');
        if (dateInput) {
            const tomorrow = new Date();
            tomorrow.setDate(tomorrow.getDate() + 1);
            dateInput.min = tomorrow.toISOString().split('T')[0];
        }

        if (window.modalManager) {
            window.modalManager.showModal('create-grant-modal');
        }
    }
}

/**
 * Revoke Grant with confirmation
 */
function revokeGrant(grantId, callerId, keyName) {
    const modal = document.getElementById('revoke-grant-modal');
    const grantInfo = document.getElementById('revoke-grant-info');
    const confirmButton = document.getElementById('confirm-revoke-grant');

    // Update modal content
    grantInfo.innerHTML = `
        <div class="grant-info-item">
            <strong>Agent/App ID:</strong> ${escapeHtml(callerId)}
        </div>
        <div class="grant-info-item">
            <strong>Key:</strong> ${escapeHtml(keyName)}
        </div>
    `;

    // Set up confirm button
    confirmButton.onclick = async () => {
        try {
            confirmButton.classList.add('loading');
            await window.grantsManager.revokeGrant(grantId);
        } catch (error) {
            // Error is already handled by the API client
        } finally {
            confirmButton.classList.remove('loading');
        }
    };

    window.modalManager.showModal('revoke-grant-modal');
}

/**
 * Handle Create Grant Form Submission
 */
async function handleCreateGrantForm(formData, form) {
    try {
        // Validate form data
        const errors = window.formValidator.validateGrantForm(formData);
        if (errors.length > 0) {
            window.formValidator.displayErrors(form, errors);
            return;
        }

        // Clear any existing errors
        window.formValidator.displayErrors(form, []);

        // Create the grant
        await window.grantsManager.createGrant(formData);

    } catch (error) {
        // Error is already handled by the API client and grantsManager
        console.error('Create grant form error:', error);
    }
}

/**
 * Filter grants by selected key
 */
function filterGrants() {
    const keyFilter = document.getElementById('key-filter');
    if (keyFilter && window.grantsManager) {
        window.grantsManager.setKeyFilter(keyFilter.value);
    }
}

// Ensure functions are available globally
window.closeModal = closeModal;
window.deleteKey = deleteKey;
window.filterGrants = filterGrants;
window.showCreateGrantForm = showCreateGrantForm;
window.revokeGrant = revokeGrant;
window.handleCreateGrantForm = handleCreateGrantForm;

/**
 * Log Entry Model class for frontend data management
 */
class LogEntry {
    constructor(data) {
        this.id = data.id || Date.now().toString();
        this.timestamp = data.timestamp ? new Date(data.timestamp) : new Date();
        this.caller_id = data.caller_id || data.agent_id || 'Unknown';
        this.key_id = data.key_id;
        this.key_name = data.key_name || 'Unknown Key';
        this.endpoint = data.endpoint || '';
        this.response_code = data.response_code || data.status || 200;
        this.response_time = data.response_time || 0;
        this.method = data.method || 'GET';
    }

    getFormattedTimestamp() {
        return this.timestamp.toLocaleString();
    }

    getStatusClass() {
        const code = this.response_code;
        if (code >= 200 && code < 300) return 'status-' + code;
        if (code >= 400 && code < 500) return 'status-' + code;
        if (code >= 500) return 'status-' + code;
        return 'status-unknown';
    }

    getResponseTimeClass() {
        if (this.response_time < 100) return 'fast';
        if (this.response_time < 1000) return 'normal';
        if (this.response_time < 3000) return 'slow';
        return 'very-slow';
    }

    getFormattedResponseTime() {
        if (this.response_time < 1000) {
            return `${this.response_time}ms`;
        }
        return `${(this.response_time / 1000).toFixed(2)}s`;
    }

    getShortEndpoint() {
        if (this.endpoint.length <= 30) return this.endpoint;
        return this.endpoint.substring(0, 27) + '...';
    }
}

/**
 * Logs Manager class for handling usage logs operations
 */
class LogsManager {
    constructor() {
        this.logs = [];
        this.filteredLogs = [];
        this.logsTableElement = document.getElementById('logs-table');
        this.logsTbodyElement = document.getElementById('logs-tbody');
        this.logsEmptyElement = document.getElementById('logs-empty');
        this.logsLoadingElement = document.getElementById('logs-loading');
        this.keyFilterElement = document.getElementById('key-filter-logs');
        this.timeFilterElement = document.getElementById('time-filter');
        
        this.currentKeyFilter = '';
        this.currentTimeFilter = '24h';
        
        this.setupEventListeners();
    }

    /**
     * Setup event listeners for filters
     */
    setupEventListeners() {
        if (this.keyFilterElement) {
            this.keyFilterElement.addEventListener('change', () => {
                this.currentKeyFilter = this.keyFilterElement.value;
                this.applyFilters();
            });
        }

        if (this.timeFilterElement) {
            this.timeFilterElement.addEventListener('change', () => {
                this.currentTimeFilter = this.timeFilterElement.value;
                this.loadLogs(); // Reload logs with new time filter
            });
        }
    }

    /**
     * Load and display logs
     */
    async loadLogs() {
        try {
            this.showLoadingState();
            
            const logsData = await window.sageAPI.getLogs(
                this.currentKeyFilter || null, 
                this.currentTimeFilter,
                this.logsLoadingElement
            );
            
            this.logs = logsData.map(logData => new LogEntry(logData));
            this.applyFilters();
            
        } catch (error) {
            console.error('Failed to load logs:', error);
            this.showEmptyState('Failed to load usage logs. Please try again.');
        } finally {
            this.hideLoadingState();
        }
    }

    /**
     * Apply current filters to logs
     */
    applyFilters() {
        let filtered = [...this.logs];

        // Apply key filter
        if (this.currentKeyFilter) {
            filtered = filtered.filter(log => log.key_id === this.currentKeyFilter);
        }

        this.filteredLogs = filtered;
        this.renderLogs();
    }

    /**
     * Render logs table
     */
    renderLogs() {
        if (this.filteredLogs.length === 0) {
            this.showEmptyState();
            return;
        }

        this.hideEmptyState();
        this.showTable();

        // Clear existing log entries
        if (this.logsTbodyElement) {
            this.logsTbodyElement.innerHTML = '';

            // Render each log entry
            this.filteredLogs.forEach(log => {
                const logRow = this.createLogRow(log);
                this.logsTbodyElement.appendChild(logRow);
            });
        }
    }

    /**
     * Create HTML row element for a log entry
     */
    createLogRow(log) {
        const row = document.createElement('tr');
        row.setAttribute('data-log-id', log.id);

        row.innerHTML = `
            <td>
                <div class="log-timestamp">${log.getFormattedTimestamp()}</div>
            </td>
            <td>
                <div class="log-caller-id">${escapeHtml(log.caller_id)}</div>
            </td>
            <td>
                <div class="log-key-name">${escapeHtml(log.key_name)}</div>
            </td>
            <td>
                <div class="log-endpoint" title="${escapeHtml(log.endpoint)}">
                    ${escapeHtml(log.getShortEndpoint())}
                </div>
            </td>
            <td>
                <div class="log-status ${log.getStatusClass()}">
                    ${log.response_code}
                </div>
            </td>
            <td>
                <div class="log-response-time ${log.getResponseTimeClass()}">
                    ${log.getFormattedResponseTime()}
                </div>
            </td>
        `;

        return row;
    }

    /**
     * Show loading state
     */
    showLoadingState() {
        this.hideTable();
        this.hideEmptyState();
        if (this.logsLoadingElement) {
            this.logsLoadingElement.style.display = 'block';
        }
    }

    /**
     * Hide loading state
     */
    hideLoadingState() {
        if (this.logsLoadingElement) {
            this.logsLoadingElement.style.display = 'none';
        }
    }

    /**
     * Show empty state
     */
    showEmptyState(message = null) {
        this.hideTable();
        this.hideLoadingState();
        
        if (this.logsEmptyElement) {
            this.logsEmptyElement.style.display = 'block';
            
            // Update message if provided
            if (message) {
                const p = this.logsEmptyElement.querySelector('p');
                if (p) {
                    p.textContent = message;
                }
            } else {
                // Default message based on filters
                const p = this.logsEmptyElement.querySelector('p');
                if (p) {
                    if (this.currentKeyFilter) {
                        p.textContent = 'No usage logs found for the selected key and time period.';
                    } else {
                        p.textContent = 'No usage logs found for the selected time period.';
                    }
                }
            }
        }
    }

    /**
     * Hide empty state
     */
    hideEmptyState() {
        if (this.logsEmptyElement) {
            this.logsEmptyElement.style.display = 'none';
        }
    }

    /**
     * Show logs table
     */
    showTable() {
        if (this.logsTableElement) {
            this.logsTableElement.style.display = 'table';
        }
    }

    /**
     * Hide logs table
     */
    hideTable() {
        if (this.logsTableElement) {
            this.logsTableElement.style.display = 'none';
        }
    }

    /**
     * Populate key filter dropdown with available keys
     */
    populateKeyFilter(keys) {
        if (!this.keyFilterElement) return;

        // Store current selection
        const currentSelection = this.keyFilterElement.value;

        // Clear existing options except the first one
        while (this.keyFilterElement.children.length > 1) {
            this.keyFilterElement.removeChild(this.keyFilterElement.lastChild);
        }

        // Add keys as options
        keys.forEach(key => {
            const option = document.createElement('option');
            option.value = key.key_id;
            option.textContent = key.getDisplayName();
            this.keyFilterElement.appendChild(option);
        });

        // Restore selection if it still exists
        if (currentSelection && keys.some(key => key.key_id === currentSelection)) {
            this.keyFilterElement.value = currentSelection;
            this.currentKeyFilter = currentSelection;
        } else {
            this.keyFilterElement.value = '';
            this.currentKeyFilter = '';
        }
    }

    /**
     * Set key filter programmatically
     */
    setKeyFilter(keyId) {
        this.currentKeyFilter = keyId;
        if (this.keyFilterElement) {
            this.keyFilterElement.value = keyId;
        }
        this.applyFilters();
    }

    /**
     * Set time filter programmatically
     */
    setTimeFilter(timeFilter) {
        this.currentTimeFilter = timeFilter;
        if (this.timeFilterElement) {
            this.timeFilterElement.value = timeFilter;
        }
        this.loadLogs(); // Reload logs with new time filter
    }

    /**
     * Refresh logs data
     */
    async refreshLogs() {
        await this.loadLogs();
    }

    /**
     * Get current filter state
     */
    getFilterState() {
        return {
            keyFilter: this.currentKeyFilter,
            timeFilter: this.currentTimeFilter
        };
    }

    /**
     * Clear all filters
     */
    clearFilters() {
        this.currentKeyFilter = '';
        this.currentTimeFilter = '24h';
        
        if (this.keyFilterElement) {
            this.keyFilterElement.value = '';
        }
        
        if (this.timeFilterElement) {
            this.timeFilterElement.value = '24h';
        }
        
        this.loadLogs();
    }
}

// LogsManager will be created in app.js when DOM is ready

/**
 * Global functions for logs management
 */

/**
 * Filter logs by key
 */
function filterLogsByKey() {
    if (window.logsManager) {
        const keyFilter = document.getElementById('key-filter-logs');
        if (keyFilter) {
            window.logsManager.setKeyFilter(keyFilter.value);
        }
    }
}

/**
 * Filter logs by time period
 */
function filterLogsByTime() {
    if (window.logsManager) {
        const timeFilter = document.getElementById('time-filter');
        if (timeFilter) {
            window.logsManager.setTimeFilter(timeFilter.value);
        }
    }
}

/**
 * Refresh logs data
 */
function refreshLogs() {
    if (window.logsManager) {
        window.logsManager.refreshLogs();
    }
}

// Make functions globally available
window.filterLogsByKey = filterLogsByKey;
window.filterLogsByTime = filterLogsByTime;
window.refreshLogs = refreshLogs;