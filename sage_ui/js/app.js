// Main application logic and initialization

/**
 * Main Application Class
 */
class SageApp {
    constructor() {
        this.currentView = 'keys';
        this.initialized = false;
        this.init();
    }
    
    /**
     * Initialize the application
     */
    init() {
        if (this.initialized) return;
        
        this.setupNavigation();
        this.setupEventListeners();
        this.loadInitialView();
        
        this.initialized = true;
        console.log('Sage UI initialized successfully');
    }
    
    /**
     * Setup navigation between views
     */
    setupNavigation() {
        const navItems = document.querySelectorAll('.nav-item');
        
        navItems.forEach((item, index) => {
            // Add ARIA attributes for accessibility
            item.setAttribute('role', 'tab');
            item.setAttribute('aria-selected', item.classList.contains('active') ? 'true' : 'false');
            item.setAttribute('tabindex', item.classList.contains('active') ? '0' : '-1');
            
            // Click handler
            item.addEventListener('click', (e) => {
                const viewName = e.target.getAttribute('data-view');
                this.switchView(viewName);
            });
            
            // Keyboard navigation
            item.addEventListener('keydown', (e) => {
                this.handleNavKeydown(e, navItems, index);
            });
        });
        
        // Set up the navigation container with ARIA attributes
        const navContainer = document.querySelector('.app-nav');
        if (navContainer) {
            navContainer.setAttribute('role', 'tablist');
            navContainer.setAttribute('aria-label', 'Main navigation');
        }
    }
    
    /**
     * Switch between different views (Keys, Grants, Logs)
     */
    switchView(viewName) {
        if (!viewName || viewName === this.currentView) return;
        
        // Validate view name
        const validViews = ['keys', 'grants', 'logs'];
        if (!validViews.includes(viewName)) {
            console.warn(`Invalid view name: ${viewName}`);
            return;
        }
        
        // Update navigation active state
        document.querySelectorAll('.nav-item').forEach(item => {
            item.classList.remove('active');
            item.setAttribute('aria-selected', 'false');
        });
        
        const activeNavItem = document.querySelector(`[data-view="${viewName}"]`);
        if (activeNavItem) {
            activeNavItem.classList.add('active');
            activeNavItem.setAttribute('aria-selected', 'true');
        }
        
        // Update view visibility with smooth transition
        document.querySelectorAll('.view').forEach(view => {
            view.classList.remove('active');
            view.setAttribute('aria-hidden', 'true');
        });
        
        const targetView = document.getElementById(`${viewName}-view`);
        if (targetView) {
            targetView.classList.add('active');
            targetView.setAttribute('aria-hidden', 'false');
            this.currentView = viewName;
            
            // Update URL hash
            this.updateURL(viewName);
            
            // Emit view change event
            appEvents.emit('viewChanged', { 
                view: viewName, 
                previousView: this.currentView 
            });
            
            // Load view-specific data (placeholder for now)
            this.loadViewData(viewName);
            
            // Focus management for accessibility
            this.manageFocus(targetView);
        }
    }
    
    /**
     * Load data for the current view
     */
    loadViewData(viewName) {
        switch (viewName) {
            case 'keys':
                this.loadKeysData();
                break;
            case 'grants':
                this.loadGrantsData();
                break;
            case 'logs':
                this.loadLogsData();
                break;
        }
    }
    
    /**
     * Load keys data
     */
    async loadKeysData() {
        console.log('Loading keys data...');
        try {
            await window.keysManager.loadKeys();
            
            // Update key filters for grants and logs managers
            if (window.grantsManager && this.currentView === 'grants') {
                window.grantsManager.populateKeyFilter(window.keysManager.keys);
            }
            
            if (window.logsManager && this.currentView === 'logs') {
                window.logsManager.populateKeyFilter(window.keysManager.keys);
            }
        } catch (error) {
            console.error('Failed to load keys data:', error);
        }
    }
    
    /**
     * Load grants data
     */
    async loadGrantsData() {
        console.log('Loading grants data...');
        try {
            // Ensure keys are loaded first
            if (!window.keysManager.keys || window.keysManager.keys.length === 0) {
                console.log('Loading keys first for grants view...');
                await window.keysManager.loadKeys();
            }
            
            // Load grants
            await window.grantsManager.loadGrants();
            
            // Populate key filter dropdown
            if (window.keysManager && window.keysManager.keys) {
                window.grantsManager.populateKeyFilter(window.keysManager.keys);
            }
            
            // Ensure grant counts are synchronized
            if (window.grantsManager && window.grantsManager.grants.length > 0) {
                window.grantsManager.updateAllKeyGrantCounts();
            }
        } catch (error) {
            console.error('Failed to load grants data:', error);
        }
    }
    
    /**
     * Load logs data
     */
    async loadLogsData() {
        console.log('Loading logs data...');
        try {
            // Ensure keys are loaded first for the filter dropdown
            if (!window.keysManager.keys || window.keysManager.keys.length === 0) {
                console.log('Loading keys first for logs view...');
                await window.keysManager.loadKeys();
            }
            
            // Populate key filter dropdown
            if (window.logsManager && window.keysManager && window.keysManager.keys) {
                window.logsManager.populateKeyFilter(window.keysManager.keys);
            }
            
            // Load logs
            if (window.logsManager) {
                await window.logsManager.loadLogs();
            }
        } catch (error) {
            console.error('Failed to load logs data:', error);
        }
    }
    
    /**
     * Setup global event listeners
     */
    setupEventListeners() {
        // Handle form submissions
        document.addEventListener('submit', (e) => {
            e.preventDefault();
            this.handleFormSubmit(e);
        });
        
        // Handle keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            this.handleKeyboardShortcuts(e);
        });
        
        // Handle window resize for responsive behavior
        window.addEventListener('resize', debounce(() => {
            this.handleResize();
        }, 250));
        
        // Setup API event listeners
        this.setupAPIEventListeners();
        
        // Setup global loading state management
        this.setupLoadingStateManagement();
        
        // Setup UI event listeners
        this.setupUIEventListeners();
    }
    
    /**
     * Setup UI-specific event listeners
     */
    setupUIEventListeners() {
        // Add Key button
        const addKeyBtn = document.getElementById('add-key-btn');
        if (addKeyBtn) {
            addKeyBtn.addEventListener('click', () => {
                console.log('Add Key button clicked');
                // Wait for modalManager to be available
                if (window.modalManager) {
                    window.modalManager.showModal('add-key-modal');
                } else {
                    // Retry after a short delay
                    setTimeout(() => {
                        if (window.modalManager) {
                            window.modalManager.showModal('add-key-modal');
                        } else {
                            console.error('modalManager still not available, showing modal directly');
                            const modal = document.getElementById('add-key-modal');
                            if (modal) {
                                modal.classList.add('active');
                            }
                        }
                    }, 100);
                }
            });
        }
        
        // Cancel buttons
        const cancelAddKeyBtn = document.getElementById('cancel-add-key');
        if (cancelAddKeyBtn) {
            cancelAddKeyBtn.addEventListener('click', () => {
                console.log('Cancel button clicked');
                if (window.modalManager) {
                    window.modalManager.closeModal();
                } else {
                    // Fallback: close modal directly
                    const modal = document.getElementById('add-key-modal');
                    if (modal) {
                        modal.classList.remove('active');
                    }
                }
                // Reset form when canceling
                const form = document.getElementById('add-key-form');
                if (form) {
                    form.reset();
                }
            });
        } else {
            console.log('Cancel button not found');
        }
        
        const cancelDeleteKeyBtn = document.getElementById('cancel-delete-key');
        if (cancelDeleteKeyBtn) {
            cancelDeleteKeyBtn.addEventListener('click', () => {
                if (window.modalManager) {
                    window.modalManager.closeModal();
                }
            });
        }
        
        // Create Grant button
        const createGrantBtn = document.getElementById('create-grant-btn');
        if (createGrantBtn) {
            createGrantBtn.addEventListener('click', () => {
                console.log('Create Grant button clicked');
                if (window.showCreateGrantForm) {
                    window.showCreateGrantForm();
                }
            });
        }

        // Cancel buttons for grants
        const cancelCreateGrantBtn = document.getElementById('cancel-create-grant');
        if (cancelCreateGrantBtn) {
            cancelCreateGrantBtn.addEventListener('click', () => {
                console.log('Cancel create grant button clicked');
                if (window.modalManager) {
                    window.modalManager.closeModal();
                }
                // Reset form when canceling
                const form = document.getElementById('create-grant-form');
                if (form) {
                    form.reset();
                }
            });
        }

        const cancelRevokeGrantBtn = document.getElementById('cancel-revoke-grant');
        if (cancelRevokeGrantBtn) {
            cancelRevokeGrantBtn.addEventListener('click', () => {
                if (window.modalManager) {
                    window.modalManager.closeModal();
                }
            });
        }

        // Key filter for grants
        const keyFilter = document.getElementById('key-filter');
        if (keyFilter) {
            keyFilter.addEventListener('change', () => {
                if (window.filterGrants) {
                    window.filterGrants();
                }
            });
        }
    }
    
    /**
     * Setup API-related event listeners
     */
    setupAPIEventListeners() {
        // Listen for API loading events
        appEvents.on('api:loading:start', (data) => {
            console.log('API request started:', data.requestId);
            window.loadingStateManager.addLoader(data.requestId);
        });
        
        appEvents.on('api:loading:end', (data) => {
            console.log('API request completed:', data.requestId);
            window.loadingStateManager.removeLoader(data.requestId);
        });
        
        // Listen for API errors
        appEvents.on('api:error', (errorInfo) => {
            console.error('API Error occurred:', errorInfo);
            // Additional error handling can be added here
        });
        
        // Listen for global loading state changes
        appEvents.on('loading:state:change', (state) => {
            this.updateGlobalLoadingIndicator(state.isLoading);
        });
    }
    
    /**
     * Setup global loading state management
     */
    setupLoadingStateManagement() {
        // Set the global loading element (could be the app container or a specific element)
        const appContainer = document.querySelector('.app-container');
        if (appContainer) {
            window.loadingStateManager.setGlobalLoadingElement(appContainer);
        }
    }
    
    /**
     * Update global loading indicator
     */
    updateGlobalLoadingIndicator(isLoading) {
        const appContainer = document.querySelector('.app-container');
        if (appContainer) {
            if (isLoading) {
                appContainer.classList.add('app-loading');
            } else {
                appContainer.classList.remove('app-loading');
            }
        }
    }
    
    /**
     * Handle form submissions
     */
    async handleFormSubmit(e) {
        const form = e.target;
        const formData = new FormData(form);
        const data = Object.fromEntries(formData.entries());
        
        // Sanitize form data
        const sanitizedData = window.requestUtils.sanitizeRequestData(data);
        
        console.log('Form submitted:', sanitizedData);
        
        try {
            // Set loading state on form
            form.classList.add('loading');
            
            // Determine form type and handle accordingly
            const formType = form.getAttribute('data-form-type');
            
            switch (formType) {
                case 'add-key':
                    await this.handleAddKeyForm(sanitizedData, form);
                    break;
                case 'create-grant':
                    await this.handleCreateGrantForm(sanitizedData, form);
                    break;
                default:
                    window.notificationManager.showInfo('Form submission will be implemented in future tasks');
            }
            
        } catch (error) {
            console.error('Form submission error:', error);
            // Error is already handled by the API client
        } finally {
            // Remove loading state from form
            form.classList.remove('loading');
        }
    }
    
    /**
     * Handle add key form submission
     */
    async handleAddKeyForm(data, form) {
        console.log('Add key form data:', data);
        try {
            // Validate form data (with fallback validation)
            const errors = this.validateKeyFormData(data);
            if (errors.length > 0) {
                this.displayFormErrors(form, errors);
                return;
            }
            
            // Clear any existing errors
            this.clearFormErrors(form);
            
            // Add the key
            if (window.keysManager) {
                await window.keysManager.addKey(data);
            } else {
                // Fallback: direct API call
                await window.sageAPI.addKey(data);
            }
            
            // Always close modal and reset form after successful submission
            if (window.modalManager) {
                window.modalManager.closeModal();
            } else {
                // Fallback: close modal directly
                const modal = document.getElementById('add-key-modal');
                if (modal) {
                    modal.classList.remove('active');
                }
            }
            form.reset();
            
        } catch (error) {
            // Error is already handled by the API client and keysManager
            console.error('Add key form error:', error);
        }
    }
    
    /**
     * Validate key form data (fallback validation)
     */
    validateKeyFormData(data) {
        const errors = [];
        
        if (!data.key_name || !data.key_name.trim()) {
            errors.push('Key name is required');
        }
        
        if (!data.environment) {
            errors.push('Environment selection is required');
        } else if (!['staging', 'prod'].includes(data.environment)) {
            errors.push('Environment must be either "staging" or "prod"');
        }
        
        if (!data.api_key || !data.api_key.trim()) {
            errors.push('API key is required');
        }
        
        return errors;
    }

    /**
     * Validate grant form data (fallback validation)
     */
    validateGrantFormData(data) {
        const errors = [];
        
        if (!data.key_id) {
            errors.push('Key selection is required');
        }
        
        if (!data.caller_agent_id || !data.caller_agent_id.trim()) {
            errors.push('Agent/App ID is required');
        } else if (!/^[a-zA-Z0-9_-]+$/.test(data.caller_agent_id)) {
            errors.push('Agent/App ID can only contain letters, numbers, underscores, and hyphens');
        }
        
        if (!data.max_calls_per_day || data.max_calls_per_day < 1) {
            errors.push('Max calls per day must be at least 1');
        }
        
        if (!data.expiry_date) {
            errors.push('Expiry date is required');
        } else if (new Date(data.expiry_date) <= new Date()) {
            errors.push('Expiry date must be in the future');
        }
        
        return errors;
    }
    
    /**
     * Display form errors (fallback error display)
     */
    displayFormErrors(form, errors) {
        // Clear existing errors
        this.clearFormErrors(form);
        
        if (errors.length === 0) return;
        
        // Show first error as general message
        const errorDiv = document.createElement('div');
        errorDiv.className = 'form-error';
        errorDiv.textContent = errors[0];
        form.insertBefore(errorDiv, form.firstChild);
        
        // Show notification
        if (window.notificationManager) {
            window.notificationManager.showError(errors[0]);
        }
    }
    
    /**
     * Clear form errors
     */
    clearFormErrors(form) {
        form.querySelectorAll('.form-error').forEach(error => error.remove());
        form.querySelectorAll('.input-error').forEach(input => input.classList.remove('input-error'));
    }
    
    /**
     * Handle create grant form submission
     */
    async handleCreateGrantForm(data, form) {
        console.log('Create grant form data:', data);
        try {
            // Validate form data (with fallback validation)
            const errors = this.validateGrantFormData(data);
            if (errors.length > 0) {
                this.displayFormErrors(form, errors);
                return;
            }

            // Clear any existing errors
            this.clearFormErrors(form);

            // Create the grant
            if (window.grantsManager) {
                await window.grantsManager.createGrant(data);
            } else {
                // Fallback: direct API call
                await window.sageAPI.createGrant(data);
            }

            // Always close modal and reset form after successful submission
            if (window.modalManager) {
                window.modalManager.closeModal();
            }
            form.reset();

        } catch (error) {
            // Error is already handled by the API client and grantsManager
            console.error('Create grant form error:', error);
        }
    }
    
    /**
     * Handle keyboard shortcuts
     */
    handleKeyboardShortcuts(e) {
        // Alt + 1/2/3 for quick navigation
        if (e.altKey && !e.ctrlKey && !e.shiftKey) {
            switch (e.key) {
                case '1':
                    e.preventDefault();
                    this.switchView('keys');
                    break;
                case '2':
                    e.preventDefault();
                    this.switchView('grants');
                    break;
                case '3':
                    e.preventDefault();
                    this.switchView('logs');
                    break;
            }
        }
    }
    
    /**
     * Handle window resize
     */
    handleResize() {
        // Responsive behavior adjustments if needed
        console.log('Window resized');
    }
    
    /**
     * Load initial view based on URL hash or default to keys
     */
    loadInitialView() {
        const hash = window.location.hash.substring(1);
        const validViews = ['keys', 'grants', 'logs'];
        const initialView = validViews.includes(hash) ? hash : 'keys';
        
        this.switchView(initialView);
    }
    
    /**
     * Update URL hash when view changes
     */
    updateURL(viewName) {
        if (history.pushState) {
            history.pushState(null, null, `#${viewName}`);
        } else {
            window.location.hash = viewName;
        }
    }
    
    /**
     * Manage focus for accessibility when switching views
     */
    manageFocus(targetView) {
        // Focus the main heading of the new view for screen readers
        const heading = targetView.querySelector('h2');
        if (heading) {
            heading.setAttribute('tabindex', '-1');
            heading.focus();
            // Remove tabindex after focus to avoid tab navigation issues
            setTimeout(() => heading.removeAttribute('tabindex'), 100);
        }
    }
    
    /**
     * Handle keyboard navigation in the nav tabs
     */
    handleNavKeydown(e, navItems, currentIndex) {
        let targetIndex = currentIndex;
        
        switch (e.key) {
            case 'ArrowLeft':
                e.preventDefault();
                targetIndex = currentIndex > 0 ? currentIndex - 1 : navItems.length - 1;
                break;
            case 'ArrowRight':
                e.preventDefault();
                targetIndex = currentIndex < navItems.length - 1 ? currentIndex + 1 : 0;
                break;
            case 'Home':
                e.preventDefault();
                targetIndex = 0;
                break;
            case 'End':
                e.preventDefault();
                targetIndex = navItems.length - 1;
                break;
            case 'Enter':
            case ' ':
                e.preventDefault();
                const viewName = navItems[currentIndex].getAttribute('data-view');
                this.switchView(viewName);
                return;
            default:
                return;
        }
        
        // Update focus and tabindex
        navItems.forEach((item, index) => {
            item.setAttribute('tabindex', index === targetIndex ? '0' : '-1');
        });
        
        navItems[targetIndex].focus();
    }
}

/**
 * Initialize the application when DOM is ready
 */
document.addEventListener('DOMContentLoaded', () => {
    console.log('DOM loaded, checking component availability:', {
        notificationManager: !!window.notificationManager,
        modalManager: !!window.modalManager,
        keysManager: !!window.keysManager
    });
    
    // Wait a bit to ensure all scripts have loaded
    setTimeout(() => {
        console.log('Initializing app, component availability:', {
            notificationManager: !!window.notificationManager,
            modalManager: !!window.modalManager,
            keysManager: !!window.keysManager
        });
        
        // Initialize GrantsManager now that DOM is ready
        if (!window.grantsManager && typeof GrantsManager !== 'undefined') {
            window.grantsManager = new GrantsManager();
            console.log('GrantsManager initialized:', !!window.grantsManager);
        }
        
        // Initialize LogsManager now that DOM is ready
        if (!window.logsManager && typeof LogsManager !== 'undefined') {
            window.logsManager = new LogsManager();
            console.log('LogsManager initialized:', !!window.logsManager);
        }
        
        // Create global app instance
        window.sageApp = new SageApp();
        
        // Show welcome message
        setTimeout(() => {
            if (window.notificationManager) {
                window.notificationManager.showSuccess('Sage UI loaded successfully! Use Alt+1/2/3 for quick navigation.');
            }
        }, 500);
    }, 100);
});

/**
 * Handle browser back/forward navigation
 */
window.addEventListener('popstate', () => {
    if (window.sageApp) {
        window.sageApp.loadInitialView();
    }
});