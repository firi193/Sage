"""
Coral MCP Interface for Sage - handles MCP protocol communication and session validation
"""

import json
import logging
import time
from datetime import datetime
from typing import Dict, Any, Optional, List
from dataclasses import asdict

from .key_manager import KeyManager
from .authorization_engine import AuthorizationEngine
from .policy_engine import PolicyEngine
from .logging_service import LoggingService
from .proxy_service import ProxyService


logger = logging.getLogger(__name__)


class CoralErrorResponse:
    """Coral-compatible error response structure"""
    
    def __init__(self, error_code: str, error_message: str, coral_session_id: str, 
                 details: Optional[Dict] = None, retry_after: Optional[int] = None):
        self.error_code = error_code
        self.error_message = error_message
        self.coral_session_id = coral_session_id
        self.details = details or {}
        self.retry_after = retry_after
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        result = {
            "error_code": self.error_code,
            "error_message": self.error_message,
            "coral_session_id": self.coral_session_id,
            "details": self.details
        }
        if self.retry_after is not None:
            result["retry_after"] = self.retry_after
        return result


class MCPInterface:
    """
    MCP protocol handler for Coral agent communication
    Handles session validation, request routing, and response formatting
    """
    
    def __init__(self, key_manager: KeyManager = None, 
                 authorization_engine: AuthorizationEngine = None,
                 policy_engine: PolicyEngine = None,
                 logging_service: LoggingService = None,
                 proxy_service: ProxyService = None):
        """
        Initialize MCP interface with required services
        
        Args:
            key_manager: Key management service
            authorization_engine: Authorization service
            policy_engine: Policy enforcement service
            logging_service: Audit logging service
            proxy_service: HTTP proxy service
        """
        self.key_manager = key_manager or KeyManager()
        self.authorization_engine = authorization_engine or AuthorizationEngine()
        self.policy_engine = policy_engine or PolicyEngine()
        self.logging_service = logging_service or LoggingService()
        self.proxy_service = proxy_service or ProxyService()
    
    async def validate_coral_session(self, session_id: str, wallet_id: Optional[str] = None) -> str:
        """
        Validate Coral session/wallet ID for caller identity
        
        Args:
            session_id: Coral session ID
            wallet_id: Optional Coral wallet ID
            
        Returns:
            Validated caller ID
            
        Raises:
            ValueError: If session validation fails
        """
        if not session_id or len(session_id.strip()) == 0:
            raise ValueError("Invalid session ID: empty or None")
        
        # For MVP, we'll do basic validation
        # In production, this would integrate with Coral's auth system
        if not session_id.startswith("coral_"):
            raise ValueError("Invalid session ID format: must start with 'coral_'")
        
        # Use wallet_id if provided, otherwise use session_id as caller_id
        caller_id = wallet_id if wallet_id else session_id
        
        logger.info(f"Validated Coral session: {session_id}, caller: {caller_id}")
        return caller_id
    
    async def handle_mcp_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle incoming MCP protocol request
        
        Args:
            request: MCP request dictionary
            
        Returns:
            MCP response dictionary
        """
        try:
            # Validate MCP request structure
            if not isinstance(request, dict):
                return self._error_response("INVALID_REQUEST", "Request must be a JSON object", "")
            
            method = request.get("method")
            params = request.get("params", {})
            session_id = request.get("session_id", "")
            
            if not method:
                return self._error_response("MISSING_METHOD", "Method is required", session_id)
            
            # Validate session
            try:
                caller_id = await self.validate_coral_session(session_id, params.get("wallet_id"))
            except ValueError as e:
                return self._error_response("AUTH_FAILED", str(e), session_id)
            
            # Route to appropriate handler
            if method == "add_key":
                return await self._handle_add_key(params, caller_id, session_id)
            elif method == "grant_access":
                return await self._handle_grant_access(params, caller_id, session_id)
            elif method == "proxy_call":
                return await self._handle_proxy_call(params, caller_id, session_id)
            elif method == "list_logs":
                return await self._handle_list_logs(params, caller_id, session_id)
            else:
                return self._error_response("UNKNOWN_METHOD", f"Unknown method: {method}", session_id)
                
        except Exception as e:
            logger.error(f"Unexpected error handling MCP request: {e}")
            return self._error_response("INTERNAL_ERROR", "Internal server error", 
                                      request.get("session_id", ""))
    
    def _error_response(self, error_code: str, error_message: str, session_id: str, 
                       details: Optional[Dict] = None, retry_after: Optional[int] = None) -> Dict[str, Any]:
        """Create standardized error response"""
        error = CoralErrorResponse(error_code, error_message, session_id, details, retry_after)
        return {
            "success": False,
            "error": error.to_dict()
        }
    
    def _success_response(self, data: Any, session_id: str) -> Dict[str, Any]:
        """Create standardized success response"""
        return {
            "success": True,
            "data": data,
            "coral_session_id": session_id
        }
    
    async def _handle_add_key(self, params: Dict[str, Any], caller_id: str, session_id: str) -> Dict[str, Any]:
        """Handle add_key MCP request"""
        try:
            key_name = params.get("key_name")
            api_key = params.get("api_key")
            
            if not key_name or not api_key:
                return self._error_response("MISSING_PARAMS", "key_name and api_key are required", session_id)
            
            # Store the key
            key_id = await self.key_manager.store_key(key_name, api_key, caller_id, session_id)
            
            # Log the operation (using proxy call method for now)
            try:
                await self.logging_service.log_proxy_call(
                    caller_id, key_id, "STORE_KEY", "/sage/add_key", 0, 0.0, 200
                )
            except Exception:
                pass  # Don't fail on logging errors
            
            return self._success_response({"key_id": key_id}, session_id)
            
        except Exception as e:
            logger.error(f"Error adding key: {e}")
            return self._error_response("KEY_STORAGE_FAILED", str(e), session_id)
    
    async def _handle_grant_access(self, params: Dict[str, Any], caller_id: str, session_id: str) -> Dict[str, Any]:
        """Handle grant_access MCP request"""
        try:
            key_id = params.get("key_id")
            target_caller_id = params.get("caller_id")
            permissions = params.get("permissions", {})
            expiry_hours = params.get("expiry_hours", 24)
            
            if not key_id or not target_caller_id:
                return self._error_response("MISSING_PARAMS", "key_id and caller_id are required", session_id)
            
            # Verify key ownership
            if not await self.key_manager.verify_key_ownership(key_id, caller_id):
                return self._error_response("UNAUTHORIZED", "You don't own this key", session_id)
            
            # Create the grant
            from datetime import datetime, timedelta
            expiry = datetime.utcnow() + timedelta(hours=expiry_hours)
            
            grant_id = await self.authorization_engine.create_grant(
                key_id, target_caller_id, permissions, expiry, caller_id
            )
            
            # Log the operation
            try:
                await self.logging_service.log_grant_access(
                    caller_id, key_id, target_caller_id, permissions
                )
            except Exception:
                pass  # Don't fail on logging errors
            
            return self._success_response({"grant_id": grant_id}, session_id)
            
        except Exception as e:
            logger.error(f"Error granting access: {e}")
            return self._error_response("GRANT_FAILED", str(e), session_id)
    
    async def _handle_proxy_call(self, params: Dict[str, Any], caller_id: str, session_id: str) -> Dict[str, Any]:
        """Handle proxy_call MCP request with integrated proxy functionality"""
        start_time = time.time()
        
        try:
            key_id = params.get("key_id")
            target_url = params.get("target_url")
            method = params.get("method", "GET")
            headers = params.get("headers", {})
            payload = params.get("payload", {})
            
            if not key_id or not target_url:
                return self._error_response("MISSING_PARAMS", "key_id and target_url are required", session_id)
            
            # Check authorization
            if not await self.authorization_engine.check_authorization(key_id, caller_id):
                try:
                    from urllib.parse import urlparse
                    endpoint = urlparse(target_url).path
                    await self.logging_service.log_authorization_failed(
                        caller_id, key_id, method, endpoint, "Access denied"
                    )
                except Exception:
                    pass  # Don't fail on logging errors
                return self._error_response("UNAUTHORIZED", "Access denied for this key", session_id)
            
            # Get the grant for rate limit checking
            grant = await self.authorization_engine.get_grant(key_id, caller_id)
            if not grant:
                return self._error_response("UNAUTHORIZED", "No valid grant found", session_id)
            
            # Check rate limits
            if not await self.policy_engine.check_rate_limit(key_id, caller_id, grant):
                try:
                    current_usage = await self.policy_engine.get_current_usage(key_id, caller_id)
                    rate_limit = grant.permissions.get("max_calls_per_day", 100)
                    from urllib.parse import urlparse
                    endpoint = urlparse(target_url).path
                    await self.logging_service.log_rate_limit_blocked(
                        caller_id, key_id, method, endpoint, current_usage, rate_limit
                    )
                except Exception:
                    pass  # Don't fail on logging errors
                return self._error_response("RATE_LIMIT_EXCEEDED", "Daily rate limit exceeded", 
                                          session_id, retry_after=86400)  # 24 hours
            
            # Retrieve the API key
            api_key = await self.key_manager._retrieve_key_for_proxy(key_id)
            
            # Make the proxied call
            response_data, response_time, payload_size = await self.proxy_service.make_proxied_call(
                target_url, method, headers, payload, api_key
            )
            
            # Increment usage counter
            await self.policy_engine.increment_usage(key_id, caller_id)
            
            # Log the API call
            from urllib.parse import urlparse
            endpoint = urlparse(target_url).path
            await self.logging_service.log_proxy_call(
                caller_id, key_id, method, endpoint, payload_size, 
                response_time, response_data.get("status_code", 200)
            )
            
            # Return response without exposing key details
            return self._success_response({
                "status_code": response_data.get("status_code"),
                "headers": response_data.get("headers", {}),
                "data": response_data.get("data"),
                "response_time_ms": response_time
            }, session_id)
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            logger.error(f"Error in proxy call: {e}")
            
            # Log the failed call
            try:
                from urllib.parse import urlparse
                endpoint = urlparse(params.get("target_url", "")).path
                await self.logging_service.log_proxy_call(
                    caller_id, params.get("key_id", ""), params.get("method", "GET"), 
                    endpoint, 0, response_time, 500, str(e)
                )
            except:
                pass  # Don't fail on logging errors
            
            return self._error_response("PROXY_CALL_FAILED", str(e), session_id)
    
    async def _handle_list_logs(self, params: Dict[str, Any], caller_id: str, session_id: str) -> Dict[str, Any]:
        """Handle list_logs MCP request"""
        try:
            key_id = params.get("key_id")
            filters = params.get("filters", {})
            
            if not key_id:
                return self._error_response("MISSING_PARAMS", "key_id is required", session_id)
            
            # Verify key ownership
            if not await self.key_manager.verify_key_ownership(key_id, caller_id):
                return self._error_response("UNAUTHORIZED", "You can only view logs for your own keys", session_id)
            
            # Add key_id to filters
            filters["key_id"] = key_id
            
            # Query logs
            logs = await self.logging_service.get_logs_for_key(key_id, caller_id)
            
            # Convert logs to dictionaries for JSON serialization
            log_data = []
            for log in logs:
                if hasattr(log, '__dict__'):
                    log_dict = asdict(log) if hasattr(log, '__dataclass_fields__') else log.__dict__
                else:
                    log_dict = log
                log_data.append(log_dict)
            
            return self._success_response({"logs": log_data}, session_id)
            
        except Exception as e:
            logger.error(f"Error listing logs: {e}")
            return self._error_response("LOG_QUERY_FAILED", str(e), session_id)
    
