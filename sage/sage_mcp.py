"""
Main SageMCP class - integrates all services for secure API key management and proxying
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List

from .services.key_manager import KeyManager
from .services.authorization_engine import AuthorizationEngine
from .services.policy_engine import PolicyEngine
from .services.logging_service import LoggingService
from .services.proxy_service import ProxyService
from .services.mcp_interface import MCPInterface, CoralErrorResponse


logger = logging.getLogger(__name__)


class SageMCP:
    """
    Main Sage MCP class that integrates all services for secure API key management
    Provides the four core methods: add_key, grant_access, proxy_call, list_logs
    """
    
    def __init__(self, 
                 key_manager: Optional[KeyManager] = None,
                 authorization_engine: Optional[AuthorizationEngine] = None,
                 policy_engine: Optional[PolicyEngine] = None,
                 logging_service: Optional[LoggingService] = None,
                 proxy_service: Optional[ProxyService] = None):
        """
        Initialize SageMCP with all required services
        
        Args:
            key_manager: Key management service (creates default if None)
            authorization_engine: Authorization service (creates default if None)
            policy_engine: Policy enforcement service (creates default if None)
            logging_service: Audit logging service (creates default if None)
            proxy_service: HTTP proxy service (creates default if None)
        """
        # Initialize services with defaults if not provided
        self.key_manager = key_manager or KeyManager()
        self.authorization_engine = authorization_engine or AuthorizationEngine()
        self.policy_engine = policy_engine or PolicyEngine()
        self.logging_service = logging_service or LoggingService()
        self.proxy_service = proxy_service or ProxyService()
        
        # Initialize MCP interface with all services
        self.mcp_interface = MCPInterface(
            key_manager=self.key_manager,
            authorization_engine=self.authorization_engine,
            policy_engine=self.policy_engine,
            logging_service=self.logging_service,
            proxy_service=self.proxy_service
        )
        
        logger.info("SageMCP initialized with all services")
    
    async def add_key(self, key_name: str, api_key: str, owner_session: str) -> str:
        """
        Encrypts and stores a new API key, returns key_id
        
        Args:
            key_name: Human-readable name for the key
            api_key: The actual API key to encrypt and store
            owner_session: Coral session ID of the key owner
            
        Returns:
            key_id: Unique identifier for the stored key
            
        Raises:
            ValueError: If parameters are invalid
            RuntimeError: If key storage fails
        """
        try:
            # Validate Coral session
            owner_id = await self.mcp_interface.validate_coral_session(owner_session)
            
            # Store the key using KeyManager
            key_id = await self.key_manager.store_key(
                key_name=key_name,
                api_key=api_key,
                owner_id=owner_id,
                coral_session_id=owner_session
            )
            
            # Log the key addition operation
            try:
                await self.logging_service.log_proxy_call(
                    caller_id=owner_id,
                    key_id=key_id,
                    method="POST",
                    endpoint="/sage/add_key",
                    payload_size=len(key_name.encode('utf-8')),
                    response_time=0.0,
                    response_code=200
                )
            except Exception as log_error:
                logger.warning(f"Failed to log add_key operation: {log_error}")
                # Don't fail the operation due to logging errors
            
            logger.info(f"Successfully added key '{key_name}' for owner {owner_id}")
            return key_id
            
        except ValueError as e:
            logger.error(f"Validation error in add_key: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in add_key: {e}")
            raise RuntimeError(f"Failed to add key: {str(e)}")
    
    async def grant_access(self, key_id: str, caller_id: str, permissions: Dict[str, Any], 
                          expiry: int, owner_session: str) -> bool:
        """
        Creates a grant for another agent with permissions and expiry
        
        Args:
            key_id: ID of the key to grant access to
            caller_id: Coral ID of the agent receiving access
            permissions: Dictionary containing permission settings (e.g., max_calls_per_day)
            expiry: Expiry time in hours from now
            owner_session: Coral session ID of the key owner
            
        Returns:
            True if grant creation successful, False otherwise
            
        Raises:
            ValueError: If parameters are invalid or key not owned by owner
            RuntimeError: If grant creation fails
        """
        try:
            # Validate Coral session
            owner_id = await self.mcp_interface.validate_coral_session(owner_session)
            
            # Verify key ownership
            if not await self.key_manager.verify_key_ownership(key_id, owner_id):
                raise ValueError("Key not found or access denied")
            
            # Validate permissions
            if not isinstance(permissions, dict):
                raise ValueError("Permissions must be a dictionary")
            
            if 'max_calls_per_day' not in permissions:
                raise ValueError("Permissions must include max_calls_per_day")
            
            if not isinstance(permissions['max_calls_per_day'], int) or permissions['max_calls_per_day'] <= 0:
                raise ValueError("max_calls_per_day must be a positive integer")
            
            # Calculate expiry datetime
            expires_at = datetime.utcnow() + timedelta(hours=expiry)
            
            # Create the grant
            grant_id = await self.authorization_engine.create_grant(
                key_id=key_id,
                caller_id=caller_id,
                permissions=permissions,
                expires_at=expires_at,
                owner_id=owner_id
            )
            
            # Log the grant operation
            try:
                await self.logging_service.log_grant_access(
                    caller_id=owner_id,
                    key_id=key_id,
                    granted_to=caller_id,
                    permissions=permissions
                )
            except Exception as log_error:
                logger.warning(f"Failed to log grant_access operation: {log_error}")
                # Don't fail the operation due to logging errors
            
            logger.info(f"Successfully granted access to key {key_id} for caller {caller_id}")
            return True
            
        except ValueError as e:
            logger.error(f"Validation error in grant_access: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in grant_access: {e}")
            raise RuntimeError(f"Failed to grant access: {str(e)}")
    
    async def proxy_call(self, key_id: str, target_url: str, payload: Dict[str, Any], 
                        caller_session: str) -> Dict[str, Any]:
        """
        Injects API key, enforces policy, forwards request, returns response
        
        Args:
            key_id: ID of the key to use for the API call
            target_url: Target API URL
            payload: Request payload dictionary
            caller_session: Coral session ID of the calling agent
            
        Returns:
            Dictionary containing response data, status code, and metadata
            
        Raises:
            ValueError: If parameters are invalid
            RuntimeError: If authorization fails, rate limits exceeded, or proxy call fails
        """
        import time
        from urllib.parse import urlparse
        
        start_time = time.time()
        
        try:
            # Validate Coral session
            caller_id = await self.mcp_interface.validate_coral_session(caller_session)
            
            # Validate required parameters
            if not key_id or not target_url:
                raise ValueError("key_id and target_url are required")
            
            # Parse URL for logging
            parsed_url = urlparse(target_url)
            endpoint = parsed_url.path or "/"
            method = payload.get('method', 'GET').upper()
            headers = payload.get('headers', {})
            body = payload.get('body', {})
            
            # Check authorization
            if not await self.authorization_engine.check_authorization(key_id, caller_id):
                # Log authorization failure
                try:
                    await self.logging_service.log_authorization_failed(
                        caller_id=caller_id,
                        key_id=key_id,
                        method=method,
                        endpoint=endpoint,
                        reason="Access denied - no valid grant"
                    )
                except Exception:
                    pass  # Don't fail on logging errors
                
                raise RuntimeError("Access denied for this key")
            
            # Get the grant for rate limit checking
            grant = await self.authorization_engine.get_grant(key_id, caller_id)
            if not grant:
                raise RuntimeError("No valid grant found")
            
            # Check rate limits
            if not await self.policy_engine.check_rate_limit(key_id, caller_id, grant):
                current_usage = await self.policy_engine.get_current_usage(key_id, caller_id)
                rate_limit = grant.permissions.get("max_calls_per_day", 100)
                
                # Log rate limit block
                try:
                    await self.logging_service.log_rate_limit_blocked(
                        caller_id=caller_id,
                        key_id=key_id,
                        method=method,
                        endpoint=endpoint,
                        current_usage=current_usage,
                        limit=rate_limit
                    )
                except Exception:
                    pass  # Don't fail on logging errors
                
                raise RuntimeError(f"Daily rate limit exceeded: {current_usage}/{rate_limit} calls")
            
            # Retrieve the API key for proxy injection
            api_key = await self.key_manager._retrieve_key_for_proxy(key_id)
            
            # Make the proxied call
            response_data, response_time, payload_size = await self.proxy_service.make_proxied_call(
                target_url=target_url,
                method=method,
                headers=headers,
                body=body,
                api_key=api_key
            )
            
            # Increment usage counter
            await self.policy_engine.increment_usage(
                key_id=key_id,
                caller_id=caller_id,
                payload_size=payload_size,
                response_time=response_time
            )
            
            # Log the successful API call
            await self.logging_service.log_proxy_call(
                caller_id=caller_id,
                key_id=key_id,
                method=method,
                endpoint=endpoint,
                payload_size=payload_size,
                response_time=response_time,
                response_code=response_data.get("status_code", 200)
            )
            
            # Return response without exposing key details
            result = {
                "status_code": response_data.get("status_code"),
                "headers": response_data.get("headers", {}),
                "data": response_data.get("data"),
                "response_time_ms": response_time,
                "success": True
            }
            
            logger.info(f"Successfully proxied call to {target_url} for caller {caller_id}")
            return result
            
        except ValueError as e:
            logger.error(f"Validation error in proxy_call: {e}")
            raise
        except RuntimeError as e:
            logger.error(f"Runtime error in proxy_call: {e}")
            raise
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            logger.error(f"Unexpected error in proxy_call: {e}")
            
            # Log the failed call
            try:
                await self.logging_service.log_proxy_call(
                    caller_id=caller_session,  # Use session as fallback
                    key_id=key_id,
                    method=payload.get('method', 'GET'),
                    endpoint=urlparse(target_url).path or "/",
                    payload_size=0,
                    response_time=response_time,
                    response_code=500,
                    error_message=str(e)
                )
            except Exception:
                pass  # Don't fail on logging errors
            
            raise RuntimeError(f"Proxy call failed: {str(e)}")
    
    async def list_logs(self, key_id: str, filters: Dict[str, Any], owner_session: str) -> List[Dict[str, Any]]:
        """
        Returns filtered audit logs for the key owner
        
        Args:
            key_id: ID of the key to get logs for
            filters: Dictionary containing filter parameters (caller_id, start_date, end_date, etc.)
            owner_session: Coral session ID of the key owner
            
        Returns:
            List of audit log dictionaries
            
        Raises:
            ValueError: If parameters are invalid or key not owned by owner
            RuntimeError: If log retrieval fails
        """
        try:
            # Validate Coral session
            owner_id = await self.mcp_interface.validate_coral_session(owner_session)
            
            # Verify key ownership
            if not await self.key_manager.verify_key_ownership(key_id, owner_id):
                raise ValueError("Key not found or access denied")
            
            # Parse filters
            start_date = None
            end_date = None
            caller_id = filters.get('caller_id')
            action = filters.get('action')
            limit = filters.get('limit', 100)
            
            # Parse date filters if provided
            if 'start_date' in filters:
                try:
                    start_date = datetime.fromisoformat(filters['start_date'])
                except (ValueError, TypeError):
                    logger.warning(f"Invalid start_date format: {filters['start_date']}")
            
            if 'end_date' in filters:
                try:
                    end_date = datetime.fromisoformat(filters['end_date'])
                except (ValueError, TypeError):
                    logger.warning(f"Invalid end_date format: {filters['end_date']}")
            
            # Validate limit
            if not isinstance(limit, int) or limit <= 0 or limit > 1000:
                limit = 100
            
            # Get logs from logging service
            logs = await self.logging_service.get_logs_for_key(
                key_id=key_id,
                owner_id=owner_id,
                start_date=start_date,
                end_date=end_date,
                caller_id=caller_id,
                action=action,
                limit=limit
            )
            
            logger.info(f"Retrieved {len(logs)} logs for key {key_id}")
            return logs
            
        except ValueError as e:
            logger.error(f"Validation error in list_logs: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in list_logs: {e}")
            raise RuntimeError(f"Failed to retrieve logs: {str(e)}")
    
    # Additional utility methods for comprehensive error handling and management
    
    async def revoke_key(self, key_id: str, owner_session: str) -> bool:
        """
        Revoke a key and all associated grants
        
        Args:
            key_id: ID of the key to revoke
            owner_session: Coral session ID of the key owner
            
        Returns:
            True if revocation successful, False otherwise
        """
        try:
            # Validate Coral session
            owner_id = await self.mcp_interface.validate_coral_session(owner_session)
            
            # Revoke the key
            success = await self.key_manager.revoke_key(key_id, owner_id)
            
            if success:
                # Revoke all grants for this key
                await self.authorization_engine.revoke_grants_for_key(key_id, owner_id)
                
                # Log the revocation
                try:
                    await self.logging_service.log_proxy_call(
                        caller_id=owner_id,
                        key_id=key_id,
                        method="DELETE",
                        endpoint="/sage/revoke_key",
                        payload_size=0,
                        response_time=0.0,
                        response_code=200
                    )
                except Exception:
                    pass  # Don't fail on logging errors
                
                logger.info(f"Successfully revoked key {key_id} and all grants")
            
            return success
            
        except Exception as e:
            logger.error(f"Error revoking key {key_id}: {e}")
            return False
    
    async def list_keys(self, owner_session: str) -> List[Dict[str, Any]]:
        """
        List all keys for an owner (metadata only)
        
        Args:
            owner_session: Coral session ID of the key owner
            
        Returns:
            List of key metadata dictionaries
        """
        try:
            # Validate Coral session
            owner_id = await self.mcp_interface.validate_coral_session(owner_session)
            
            # Get keys from key manager
            keys = await self.key_manager.list_keys(owner_id)
            
            logger.info(f"Listed {len(keys)} keys for owner {owner_id}")
            return keys
            
        except Exception as e:
            logger.error(f"Error listing keys: {e}")
            return []
    
    async def get_usage_stats(self, key_id: str, owner_session: str, 
                            days: int = 7) -> Dict[str, Any]:
        """
        Get usage statistics for a key
        
        Args:
            key_id: ID of the key
            owner_session: Coral session ID of the key owner
            days: Number of days to include in statistics
            
        Returns:
            Dictionary with usage statistics
        """
        try:
            # Validate Coral session
            owner_id = await self.mcp_interface.validate_coral_session(owner_session)
            
            # Verify key ownership
            if not await self.key_manager.verify_key_ownership(key_id, owner_id):
                raise ValueError("Key not found or access denied")
            
            # Calculate date range
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=days)
            
            # Get usage statistics
            stats = await self.logging_service.get_usage_statistics(
                key_id=key_id,
                owner_id=owner_id,
                start_date=start_date,
                end_date=end_date
            )
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting usage stats for key {key_id}: {e}")
            return {}
    
    async def cleanup_expired_grants(self) -> int:
        """
        Clean up expired grants (maintenance operation)
        
        Returns:
            Number of grants cleaned up
        """
        try:
            count = await self.authorization_engine.cleanup_expired_grants()
            logger.info(f"Cleaned up {count} expired grants")
            return count
        except Exception as e:
            logger.error(f"Error cleaning up expired grants: {e}")
            return 0
    
    async def close(self):
        """
        Close all services and cleanup resources
        """
        try:
            await self.proxy_service.close()
            logger.info("SageMCP services closed successfully")
        except Exception as e:
            logger.error(f"Error closing SageMCP services: {e}")
    
    # MCP Protocol Handler
    async def handle_mcp_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle MCP protocol requests through the MCP interface
        
        Args:
            request: MCP request dictionary
            
        Returns:
            MCP response dictionary
        """
        return await self.mcp_interface.handle_mcp_request(request)