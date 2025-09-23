"""
Integration tests for MCP Interface with all services
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from datetime import datetime, timedelta

from sage.services.mcp_interface import MCPInterface
from sage.services.key_manager import KeyManager
from sage.services.authorization_engine import AuthorizationEngine
from sage.services.policy_engine import PolicyEngine
from sage.services.logging_service import LoggingService
from sage.services.proxy_service import ProxyService


class TestMCPIntegration:
    """Integration tests for complete MCP workflow"""
    
    @pytest.fixture
    def mcp_interface(self):
        """Create MCP interface with mocked services"""
        # Create mocked services to avoid database dependencies
        key_manager = AsyncMock()
        authorization_engine = AsyncMock()
        policy_engine = AsyncMock()
        logging_service = AsyncMock()
        proxy_service = AsyncMock()
        
        # Add required methods
        key_manager.store_key = AsyncMock()
        key_manager.verify_key_ownership = AsyncMock()
        key_manager._retrieve_key_for_proxy = AsyncMock()
        
        authorization_engine.create_grant = AsyncMock()
        authorization_engine.check_authorization = AsyncMock()
        authorization_engine.get_grant = AsyncMock()
        
        policy_engine.check_rate_limit = AsyncMock()
        policy_engine.get_current_usage = AsyncMock()
        policy_engine.increment_usage = AsyncMock()
        
        logging_service.log_proxy_call = AsyncMock()
        logging_service.log_grant_access = AsyncMock()
        logging_service.log_rate_limit_blocked = AsyncMock()
        logging_service.log_authorization_failed = AsyncMock()
        logging_service.get_logs_for_key = AsyncMock()
        
        proxy_service.make_proxied_call = AsyncMock()
        proxy_service.close = AsyncMock()
        
        interface = MCPInterface(
            key_manager=key_manager,
            authorization_engine=authorization_engine,
            policy_engine=policy_engine,
            logging_service=logging_service,
            proxy_service=proxy_service
        )
        
        return interface
    
    @pytest.mark.asyncio
    async def test_complete_workflow(self, mcp_interface):
        """Test complete workflow: add key -> grant access -> proxy call -> list logs"""
        
        # Mock service responses
        key_id = "key_123"
        grant_id = "grant_456"
        
        # Mock key manager
        mcp_interface.key_manager.store_key.return_value = key_id
        mcp_interface.key_manager.verify_key_ownership.return_value = True
        mcp_interface.key_manager._retrieve_key_for_proxy.return_value = "sk-test123"
        
        # Mock authorization engine
        mcp_interface.authorization_engine.create_grant.return_value = grant_id
        mcp_interface.authorization_engine.check_authorization.return_value = True
        
        # Create a mock grant object
        from sage.models.access_grant import AccessGrant
        mock_grant = AccessGrant(
            grant_id=grant_id,
            key_id=key_id,
            caller_id="coral_agent_caller",
            permissions={"max_calls_per_day": 100},
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(hours=24),
            is_active=True,
            granted_by="coral_session_owner"
        )
        mcp_interface.authorization_engine.get_grant.return_value = mock_grant
        
        # Mock policy engine
        mcp_interface.policy_engine.check_rate_limit.return_value = True
        mcp_interface.policy_engine.get_current_usage.return_value = 5
        
        # Mock logging service
        mcp_interface.logging_service.get_logs_for_key.return_value = [
            {"log_id": "log_1", "timestamp": datetime.utcnow().isoformat(), "action": "proxy_call"}
        ]
        
        # Step 1: Add API key
        add_key_request = {
            "method": "add_key",
            "session_id": "coral_session_owner",
            "params": {
                "key_name": "openai_key",
                "api_key": "sk-test123"
            }
        }
        
        result = await mcp_interface.handle_mcp_request(add_key_request)
        assert result["success"] is True
        assert "key_id" in result["data"]
        
        # Step 2: Grant access to another agent
        grant_request = {
            "method": "grant_access",
            "session_id": "coral_session_owner",
            "params": {
                "key_id": key_id,
                "caller_id": "coral_agent_caller",
                "permissions": {"max_calls_per_day": 100},
                "expiry_hours": 24
            }
        }
        
        result = await mcp_interface.handle_mcp_request(grant_request)
        assert result["success"] is True
        assert "grant_id" in result["data"]
        
        # Step 3: Make a proxy call (mock the HTTP request)
        with patch.object(mcp_interface.proxy_service, 'make_proxied_call') as mock_proxy:
            mock_proxy.return_value = (
                {"status_code": 200, "data": {"result": "success"}, "headers": {}},
                150.0,  # response time
                512     # payload size
            )
            
            proxy_request = {
                "method": "proxy_call",
                "session_id": "coral_agent_caller",
                "params": {
                    "key_id": key_id,
                    "target_url": "https://api.openai.com/v1/chat/completions",
                    "method": "POST",
                    "payload": {"model": "gpt-3.5-turbo", "messages": [{"role": "user", "content": "Hello"}]}
                }
            }
            
            result = await mcp_interface.handle_mcp_request(proxy_request)
            assert result["success"] is True
            assert result["data"]["status_code"] == 200
            assert result["data"]["data"]["result"] == "success"
            
            # Verify proxy call was made with correct parameters
            mock_proxy.assert_called_once()
            call_args = mock_proxy.call_args[0]  # positional arguments
            assert "api.openai.com" in call_args[0]  # target_url
            assert call_args[1] == "POST"  # method
            assert call_args[4] == "sk-test123"  # api_key
        
        # Step 4: List logs
        logs_request = {
            "method": "list_logs",
            "session_id": "coral_session_owner",
            "params": {
                "key_id": key_id,
                "filters": {}
            }
        }
        
        result = await mcp_interface.handle_mcp_request(logs_request)
        assert result["success"] is True
        assert "logs" in result["data"]
        assert len(result["data"]["logs"]) > 0
    
    @pytest.mark.asyncio
    async def test_unauthorized_access_flow(self, mcp_interface):
        """Test that unauthorized access is properly blocked"""
        
        key_id = "key_123"
        
        # Mock that authorization fails
        mcp_interface.authorization_engine.check_authorization.return_value = False
        
        proxy_request = {
            "method": "proxy_call",
            "session_id": "coral_unauthorized_agent",
            "params": {
                "key_id": key_id,
                "target_url": "https://api.openai.com/v1/chat/completions"
            }
        }
        
        result = await mcp_interface.handle_mcp_request(proxy_request)
        assert result["success"] is False
        assert result["error"]["error_code"] == "UNAUTHORIZED"
    
    @pytest.mark.asyncio
    async def test_rate_limit_enforcement(self, mcp_interface):
        """Test that rate limits are properly enforced"""
        
        key_id = "key_123"
        
        # Mock that authorization passes but rate limit fails
        mcp_interface.authorization_engine.check_authorization.return_value = True
        
        # Create a mock grant for rate limit checking
        from sage.models.access_grant import AccessGrant
        mock_grant = AccessGrant(
            grant_id="grant_123",
            key_id=key_id,
            caller_id="coral_agent_caller",
            permissions={"max_calls_per_day": 100},
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(hours=24),
            is_active=True,
            granted_by="owner_123"
        )
        mcp_interface.authorization_engine.get_grant.return_value = mock_grant
        mcp_interface.policy_engine.check_rate_limit.return_value = False
        mcp_interface.policy_engine.get_current_usage.return_value = 150
        
        proxy_request = {
            "method": "proxy_call",
            "session_id": "coral_agent_caller",
            "params": {
                "key_id": key_id,
                "target_url": "https://api.openai.com/v1/chat/completions"
            }
        }
        
        result = await mcp_interface.handle_mcp_request(proxy_request)
        assert result["success"] is False
        assert result["error"]["error_code"] == "RATE_LIMIT_EXCEEDED"
        assert result["error"]["retry_after"] == 86400  # 24 hours
    
    @pytest.mark.asyncio
    async def test_session_validation(self, mcp_interface):
        """Test Coral session validation"""
        
        # Test valid session
        valid_session = "coral_session_123"
        caller_id = await mcp_interface.validate_coral_session(valid_session)
        assert caller_id == valid_session
        
        # Test valid session with wallet ID
        wallet_id = "wallet_456"
        caller_id = await mcp_interface.validate_coral_session(valid_session, wallet_id)
        assert caller_id == wallet_id
        
        # Test invalid session format
        with pytest.raises(ValueError):
            await mcp_interface.validate_coral_session("invalid_session")
        
        # Test empty session
        with pytest.raises(ValueError):
            await mcp_interface.validate_coral_session("")
    
    @pytest.mark.asyncio
    async def test_error_handling_and_logging(self, mcp_interface):
        """Test that errors are properly handled and logged"""
        
        # Mock service to raise an exception
        mcp_interface.key_manager.store_key.side_effect = Exception("Database error")
        
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
        assert "Database error" in result["error"]["error_message"]