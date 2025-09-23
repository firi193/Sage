"""
Unit tests for MCPInterface
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timedelta

from sage.services.mcp_interface import MCPInterface, CoralErrorResponse
from sage.services.key_manager import KeyManager
from sage.services.authorization_engine import AuthorizationEngine
from sage.services.policy_engine import PolicyEngine
from sage.services.logging_service import LoggingService
from sage.services.proxy_service import ProxyService


class TestCoralErrorResponse:
    
    def test_error_response_basic(self):
        """Test basic error response creation"""
        error = CoralErrorResponse("AUTH_FAILED", "Invalid session", "coral_session_123")
        
        result = error.to_dict()
        
        assert result["error_code"] == "AUTH_FAILED"
        assert result["error_message"] == "Invalid session"
        assert result["coral_session_id"] == "coral_session_123"
        assert result["details"] == {}
        assert "retry_after" not in result
    
    def test_error_response_with_details(self):
        """Test error response with details and retry_after"""
        details = {"reason": "rate_limit", "current_usage": 150}
        error = CoralErrorResponse("RATE_LIMIT", "Too many requests", "coral_session_123", 
                                 details=details, retry_after=3600)
        
        result = error.to_dict()
        
        assert result["details"] == details
        assert result["retry_after"] == 3600


class TestMCPInterface:
    
    @pytest.fixture
    def mock_services(self):
        """Create mock services for testing"""
        key_manager = AsyncMock()
        authorization_engine = AsyncMock()
        policy_engine = AsyncMock()
        logging_service = AsyncMock()
        proxy_service = AsyncMock()
        
        # Add required methods
        logging_service.log_proxy_call = AsyncMock()
        logging_service.log_grant_access = AsyncMock()
        logging_service.log_rate_limit_blocked = AsyncMock()
        logging_service.log_authorization_failed = AsyncMock()
        logging_service.get_logs_for_key = AsyncMock()
        
        authorization_engine.get_grant = AsyncMock()
        
        return {
            'key_manager': key_manager,
            'authorization_engine': authorization_engine,
            'policy_engine': policy_engine,
            'logging_service': logging_service,
            'proxy_service': proxy_service
        }
    
    @pytest.fixture
    def mcp_interface(self, mock_services):
        """Create MCP interface with mocked services"""
        return MCPInterface(**mock_services)
    
    @pytest.mark.asyncio
    async def test_validate_coral_session_valid(self, mcp_interface):
        """Test valid Coral session validation"""
        session_id = "coral_session_123"
        wallet_id = "wallet_456"
        
        result = await mcp_interface.validate_coral_session(session_id, wallet_id)
        
        assert result == wallet_id
    
    @pytest.mark.asyncio
    async def test_validate_coral_session_no_wallet(self, mcp_interface):
        """Test Coral session validation without wallet ID"""
        session_id = "coral_session_123"
        
        result = await mcp_interface.validate_coral_session(session_id)
        
        assert result == session_id
    
    @pytest.mark.asyncio
    async def test_validate_coral_session_invalid_format(self, mcp_interface):
        """Test invalid Coral session format"""
        session_id = "invalid_session_123"
        
        with pytest.raises(ValueError, match="Invalid session ID format"):
            await mcp_interface.validate_coral_session(session_id)
    
    @pytest.mark.asyncio
    async def test_validate_coral_session_empty(self, mcp_interface):
        """Test empty Coral session ID"""
        with pytest.raises(ValueError, match="Invalid session ID: empty or None"):
            await mcp_interface.validate_coral_session("")
        
        with pytest.raises(ValueError, match="Invalid session ID: empty or None"):
            await mcp_interface.validate_coral_session(None)
    
    @pytest.mark.asyncio
    async def test_handle_mcp_request_invalid_structure(self, mcp_interface):
        """Test handling invalid MCP request structure"""
        request = "not a dict"
        
        result = await mcp_interface.handle_mcp_request(request)
        
        assert result["success"] is False
        assert result["error"]["error_code"] == "INVALID_REQUEST"
    
    @pytest.mark.asyncio
    async def test_handle_mcp_request_missing_method(self, mcp_interface):
        """Test handling MCP request without method"""
        request = {"session_id": "coral_session_123", "params": {}}
        
        result = await mcp_interface.handle_mcp_request(request)
        
        assert result["success"] is False
        assert result["error"]["error_code"] == "MISSING_METHOD"
    
    @pytest.mark.asyncio
    async def test_handle_mcp_request_invalid_session(self, mcp_interface):
        """Test handling MCP request with invalid session"""
        request = {
            "method": "add_key",
            "session_id": "invalid_session",
            "params": {}
        }
        
        result = await mcp_interface.handle_mcp_request(request)
        
        assert result["success"] is False
        assert result["error"]["error_code"] == "AUTH_FAILED"
    
    @pytest.mark.asyncio
    async def test_handle_mcp_request_unknown_method(self, mcp_interface):
        """Test handling MCP request with unknown method"""
        request = {
            "method": "unknown_method",
            "session_id": "coral_session_123",
            "params": {}
        }
        
        result = await mcp_interface.handle_mcp_request(request)
        
        assert result["success"] is False
        assert result["error"]["error_code"] == "UNKNOWN_METHOD"
    
    @pytest.mark.asyncio
    async def test_handle_add_key_success(self, mcp_interface, mock_services):
        """Test successful add_key handling"""
        mock_services['key_manager'].store_key.return_value = "key_123"
        
        request = {
            "method": "add_key",
            "session_id": "coral_session_123",
            "params": {
                "key_name": "openai_key",
                "api_key": "sk-test123"
            }
        }
        
        result = await mcp_interface.handle_mcp_request(request)
        
        assert result["success"] is True
        assert result["data"]["key_id"] == "key_123"
        mock_services['key_manager'].store_key.assert_called_once_with(
            "openai_key", "sk-test123", "coral_session_123", "coral_session_123"
        )
        mock_services['logging_service'].log_proxy_call.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_handle_add_key_missing_params(self, mcp_interface):
        """Test add_key with missing parameters"""
        request = {
            "method": "add_key",
            "session_id": "coral_session_123",
            "params": {"key_name": "openai_key"}  # Missing api_key
        }
        
        result = await mcp_interface.handle_mcp_request(request)
        
        assert result["success"] is False
        assert result["error"]["error_code"] == "MISSING_PARAMS"
    
    @pytest.mark.asyncio
    async def test_handle_grant_access_success(self, mcp_interface, mock_services):
        """Test successful grant_access handling"""
        mock_services['key_manager'].verify_key_ownership.return_value = True
        mock_services['authorization_engine'].create_grant.return_value = "grant_123"
        
        request = {
            "method": "grant_access",
            "session_id": "coral_session_123",
            "params": {
                "key_id": "key_123",
                "caller_id": "coral_agent_456",
                "permissions": {"max_calls_per_day": 100},
                "expiry_hours": 24
            }
        }
        
        result = await mcp_interface.handle_mcp_request(request)
        
        assert result["success"] is True
        assert result["data"]["grant_id"] == "grant_123"
        mock_services['key_manager'].verify_key_ownership.assert_called_once_with(
            "key_123", "coral_session_123"
        )
        mock_services['authorization_engine'].create_grant.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_handle_grant_access_unauthorized(self, mcp_interface, mock_services):
        """Test grant_access with unauthorized key access"""
        mock_services['key_manager'].verify_key_ownership.return_value = False
        
        request = {
            "method": "grant_access",
            "session_id": "coral_session_123",
            "params": {
                "key_id": "key_123",
                "caller_id": "coral_agent_456"
            }
        }
        
        result = await mcp_interface.handle_mcp_request(request)
        
        assert result["success"] is False
        assert result["error"]["error_code"] == "UNAUTHORIZED"
    
    @pytest.mark.asyncio
    async def test_handle_proxy_call_success(self, mcp_interface, mock_services):
        """Test successful proxy_call handling"""
        from sage.models.access_grant import AccessGrant
        from datetime import datetime, timedelta
        
        mock_grant = AccessGrant(
            grant_id="grant_123",
            key_id="key_123",
            caller_id="coral_session_123",
            permissions={"max_calls_per_day": 100},
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(hours=24),
            is_active=True,
            granted_by="owner_123"
        )
        
        mock_services['authorization_engine'].check_authorization.return_value = True
        mock_services['authorization_engine'].get_grant.return_value = mock_grant
        mock_services['policy_engine'].check_rate_limit.return_value = True
        mock_services['key_manager']._retrieve_key_for_proxy.return_value = "sk-test123"
        mock_services['proxy_service'].make_proxied_call.return_value = (
            {"status_code": 200, "data": {"result": "success"}, "headers": {}},
            150.5,  # response time
            1024    # payload size
        )
        
        request = {
            "method": "proxy_call",
            "session_id": "coral_session_123",
            "params": {
                "key_id": "key_123",
                "target_url": "https://api.openai.com/v1/chat/completions",
                "method": "POST",
                "payload": {"model": "gpt-3.5-turbo", "messages": []}
            }
        }
        
        result = await mcp_interface.handle_mcp_request(request)
        
        assert result["success"] is True
        assert result["data"]["status_code"] == 200
        assert result["data"]["data"] == {"result": "success"}
        assert result["data"]["response_time_ms"] == 150.5
        
        # Verify all checks were performed
        mock_services['authorization_engine'].check_authorization.assert_called_once()
        mock_services['authorization_engine'].get_grant.assert_called_once()
        mock_services['policy_engine'].check_rate_limit.assert_called_once()
        mock_services['policy_engine'].increment_usage.assert_called_once()
        mock_services['logging_service'].log_proxy_call.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_handle_proxy_call_unauthorized(self, mcp_interface, mock_services):
        """Test proxy_call with unauthorized access"""
        mock_services['authorization_engine'].check_authorization.return_value = False
        
        request = {
            "method": "proxy_call",
            "session_id": "coral_session_123",
            "params": {
                "key_id": "key_123",
                "target_url": "https://api.openai.com/v1/chat/completions"
            }
        }
        
        result = await mcp_interface.handle_mcp_request(request)
        
        assert result["success"] is False
        assert result["error"]["error_code"] == "UNAUTHORIZED"
        mock_services['logging_service'].log_authorization_failed.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_handle_proxy_call_rate_limited(self, mcp_interface, mock_services):
        """Test proxy_call with rate limit exceeded"""
        from sage.models.access_grant import AccessGrant
        from datetime import datetime, timedelta
        
        mock_grant = AccessGrant(
            grant_id="grant_123",
            key_id="key_123",
            caller_id="coral_session_123",
            permissions={"max_calls_per_day": 100},
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(hours=24),
            is_active=True,
            granted_by="owner_123"
        )
        
        mock_services['authorization_engine'].check_authorization.return_value = True
        mock_services['authorization_engine'].get_grant.return_value = mock_grant
        mock_services['policy_engine'].check_rate_limit.return_value = False
        mock_services['policy_engine'].get_current_usage.return_value = 150
        
        request = {
            "method": "proxy_call",
            "session_id": "coral_session_123",
            "params": {
                "key_id": "key_123",
                "target_url": "https://api.openai.com/v1/chat/completions"
            }
        }
        
        result = await mcp_interface.handle_mcp_request(request)
        
        assert result["success"] is False
        assert result["error"]["error_code"] == "RATE_LIMIT_EXCEEDED"
        assert result["error"]["retry_after"] == 86400  # 24 hours
        mock_services['logging_service'].log_rate_limit_blocked.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_handle_list_logs_success(self, mcp_interface, mock_services):
        """Test successful list_logs handling"""
        mock_services['key_manager'].verify_key_ownership.return_value = True
        mock_logs = [
            {"log_id": "log_1", "timestamp": datetime.utcnow().isoformat()},
            {"log_id": "log_2", "timestamp": datetime.utcnow().isoformat()}
        ]
        mock_services['logging_service'].get_logs_for_key.return_value = mock_logs
        
        request = {
            "method": "list_logs",
            "session_id": "coral_session_123",
            "params": {
                "key_id": "key_123",
                "filters": {"start_date": "2024-01-01"}
            }
        }
        
        result = await mcp_interface.handle_mcp_request(request)
        
        assert result["success"] is True
        assert len(result["data"]["logs"]) == 2
        mock_services['key_manager'].verify_key_ownership.assert_called_once_with(
            "key_123", "coral_session_123"
        )
    
    @pytest.mark.asyncio
    async def test_handle_list_logs_unauthorized(self, mcp_interface, mock_services):
        """Test list_logs with unauthorized key access"""
        mock_services['key_manager'].verify_key_ownership.return_value = False
        
        request = {
            "method": "list_logs",
            "session_id": "coral_session_123",
            "params": {"key_id": "key_123"}
        }
        
        result = await mcp_interface.handle_mcp_request(request)
        
        assert result["success"] is False
        assert result["error"]["error_code"] == "UNAUTHORIZED"
    
    @pytest.mark.asyncio
    async def test_handle_exception_in_request(self, mcp_interface, mock_services):
        """Test handling unexpected exceptions"""
        mock_services['key_manager'].store_key.side_effect = Exception("Database error")
        
        request = {
            "method": "add_key",
            "session_id": "coral_session_123",
            "params": {
                "key_name": "test_key",
                "api_key": "sk-test123"
            }
        }
        
        result = await mcp_interface.handle_mcp_request(request)
        
        assert result["success"] is False
        assert result["error"]["error_code"] == "KEY_STORAGE_FAILED"
    
    def test_success_response_format(self, mcp_interface):
        """Test success response format"""
        data = {"key_id": "key_123"}
        session_id = "coral_session_123"
        
        result = mcp_interface._success_response(data, session_id)
        
        assert result["success"] is True
        assert result["data"] == data
        assert result["coral_session_id"] == session_id
    
    def test_error_response_format(self, mcp_interface):
        """Test error response format"""
        result = mcp_interface._error_response("TEST_ERROR", "Test message", "coral_session_123")
        
        assert result["success"] is False
        assert result["error"]["error_code"] == "TEST_ERROR"
        assert result["error"]["error_message"] == "Test message"
        assert result["error"]["coral_session_id"] == "coral_session_123"