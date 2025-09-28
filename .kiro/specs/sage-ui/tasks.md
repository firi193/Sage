# Implementation Plan

- [x] 1. Set up basic project structure and static files





  - Create HTML/CSS/JS file structure in sage_ui folder
  - Implement basic HTML shell with header, navigation, and main content areas
  - Add CSS reset and basic styling framework
  - Create placeholder views for Keys, Grants, and Logs sections
  - _Requirements: 4.1, 4.2_

- [x] 2. Build core navigation and view switching functionality





  - Implement JavaScript navigation between Keys, Grants, and Logs views
  - Add active state management for navigation tabs
  - Create view switching logic with proper show/hide functionality
  - Add basic responsive layout with CSS Grid/Flexbox
  - _Requirements: 4.2, 4.3_

- [x] 3. Create API client and backend communication layer





  - Implement SageAPI class with fetch-based HTTP client
  - Add error handling for network requests and API responses
  - Create utility functions for request/response processing
  - Add loading state management for async operations
  - _Requirements: 4.4, 4.5, 4.6_

- [x] 4. Implement Keys management view and functionality






  - Build keys list display with key name, environment, and status
  - Create "Add Key" modal form with validation
  - Implement add key functionality with API integration
  - Add delete key functionality with confirmation dialog
  - Write form validation for key name, environment, and API key fields
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

- [x] 5. Build Grants management view and functionality





  - Create grants list display showing caller ID, limits, expiry, and status
  - Implement "Create Grant" modal form with key selection dropdown
  - Add grant creation functionality with API integration
  - Build grant revocation with confirmation dialog
  - Add form validation for agent/app ID, daily limits, and expiry dates
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

- [x] 6. Implement Usage Logs view and filtering





  - Build logs table display with timestamp, agent/app ID, endpoint, and status
  - Add time filter dropdown (Last 24h / Last 7d) functionality
  - Implement key filter dropdown to show logs for specific keys
  - Add "No usage yet" empty state when no logs are available
  - Create loading indicators for log data fetching
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_

- [ ] 7. Add comprehensive error handling and user feedback
  - Implement NotificationManager for success/error messages
  - Add form validation with clear error message display
  - Create proper error handling for API failures and network issues
  - Add loading states for all async operations
  - Implement user-friendly error messages for common scenarios
  - _Requirements: 4.4, 4.5, 4.6_

- [ ] 8. Create FastAPI endpoints to bridge UI and Sage MCP service
  - Add REST endpoints for keys management (GET /keys, POST /keys, DELETE /keys/{id})
  - Implement grants endpoints (GET /grants, POST /grants, DELETE /grants/{id})
  - Create logs endpoint (GET /logs) with filtering parameters
  - Add proper error handling and response formatting in FastAPI
  - Integrate endpoints with existing Sage MCP service methods
  - _Requirements: 1.1, 1.2, 1.3, 1.5, 2.1, 2.2, 2.5, 3.1, 3.2_

- [ ] 9. Add data models and state management
  - Implement frontend Key and Grant JavaScript classes
  - Add local state management for current view data
  - Create data transformation utilities for API responses
  - Implement proper data validation and sanitization
  - Add session management for user preferences
  - _Requirements: 4.3, 4.4_

- [ ] 10. Polish UI styling and responsive design
  - Complete CSS styling for all components and modals
  - Ensure responsive design works on desktop browsers
  - Add proper visual feedback for interactive elements
  - Implement consistent spacing, typography, and color scheme
  - Add loading spinners and transition animations
  - _Requirements: 4.1, 4.2, 4.5, 4.6_

- [ ] 11. Implement comprehensive form validation and security
  - Add client-side validation for all forms with clear error messages
  - Implement input sanitization to prevent XSS attacks
  - Add proper handling of sensitive data (never store API keys in browser)
  - Create session timeout and security utilities
  - Add CSRF protection considerations for forms
  - _Requirements: 1.2, 1.3, 2.2, 2.3, 4.4_

- [ ] 12. Create end-to-end testing and integration validation
  - Test complete workflow: add key → create grant → view logs
  - Validate all form submissions and error handling scenarios
  - Test responsive design across target browsers (Chrome, Firefox, Safari, Edge)
  - Verify API integration with FastAPI endpoints
  - Test edge cases like empty states, network failures, and validation errors
  - _Requirements: All requirements validation_