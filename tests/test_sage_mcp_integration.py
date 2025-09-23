"""
Integration tests for SageMCP - tests complete workflows and service integration
"""

import pytest
import pytest_asyncio
import asyncio
import tempfile
import os
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

from sage.sage_mcp import SageMCP
from sage.services.key_manager import KeyManager
from sage.services.authorization_engine import AuthorizationEngine
from sage.services.policy_engine import PolicyEngine
from sage.services.logging_service import LoggingService
from sage.services.proxy_service import ProxyService


@pytest_asyncio.fixture
async def temp_databases():
    """Create temporary database files for testing"""
    temp_dir = tempfile.mkdtemp()
    
    db_paths = {
        'keys': os.path.join(temp_dir, 'test_keys.db'),
        'grants': os.path.join(temp_dir, 'test_grants.db'),
        'policy': os.path.join(temp_dir, 'test_policy.db'),
        'logs': os.path.join(temp_dir, 'test_logs.db')
    }
    
    yield db_paths
    
    # Cleanup
    for db_path in db_paths.values():
        if os.path.exists(db_path):
            os.remove(db_path)
    os.rmdir(temp_dir)


@pytest_asyncio.fixture
async def sage_mcp(temp_databases):
    """Create SageMCP instance with temporary databases"""
    from sage.services.key_storage import KeyStorageService
    
    # Create services with temporary databases
    key_storage_service = KeyStorageService(db_path=temp_databases['keys'])
    key_manager = KeyManager(
        storage_service=key_storage_service,
        encryption_manager=None
    )
    
    authorization_engine = AuthorizationEngine(db_path=temp_databases['grants'])
    policy_engine = PolicyEngine(db_path=temp_databases['policy'])
    logging_service = LoggingService(db_path=temp_databases['logs'])
    proxy_service = ProxyService()
    
    # Create SageMCP instance
    sage = SageMCP(
        key_manager=key_manager,
        authorization_engine=authorization_engine,
        policy_engine=policy_engine,
        logging_service=logging_service,
        proxy_service=proxy_service
    )
    
    yield sage
    
    # Cleanup
    await sage.close()


class TestSageMCPIntegration:
    """Integration tests for complete SageMCP workflows"""
    
    @pytest.mark.asyncio
    async def test_complete_workflow_agent_a_to_agent_b(self, sage_mcp):
        """
        Test complete workflow: Agent A stores key → grants access to Agent B → Agent B makes calls
        """
        # Agent A credentials
        agent_a_session = "coral_agent_a_session_123"
        agent_a_key_name = "openai_api_key"
        agent_a_api_key = "sk-test123456789"
        
        # Agent B credentials
        agent_b_session = "coral_agent_b_session_456"
        
        # Step 1: Agent A stores their API key
        key_id = await sage_mcp.add_key(
            key_name=agent_a_key_name,
            api_key=agent_a_api_key,
            owner_session=agent_a_session
        )
        
        assert key_id is not None
        assert isinstance(key_id, str)
        assert len(key_id) > 0
        
        # Step 2: Agent A grants access to Agent B
        permissions = {"max_calls_per_day": 10}
        grant_success = await sage_mcp.grant_access(
            key_id=key_id,
            caller_id=agent_b_session,
            permissions=permissions,
            expiry=24,  # 24 hours
            owner_session=agent_a_session
        )
        
        assert grant_success is True
        
        # Step 3: Mock external API call for Agent B's proxy call
        mock_response = {
            "status_code": 200,
            "headers": {"content-type": "application/json"},
            "data": {"message": "Hello from OpenAI"}
        }
        
        with patch.object(sage_mcp.proxy_service, 'make_proxied_call', 
                         return_value=(mock_response, 150.0, 100)) as mock_call:
            
            # Step 4: Agent B makes a successful proxy call
            response = await sage_mcp.proxy_call(
                key_id=key_id,
                target_url="https://api.openai.com/v1/chat/completions",
                payload={
                    "method": "POST",
                    "headers": {"Content-Type": "application/json"},
                    "body": {"model": "gpt-3.5-turbo", "messages": []}
                },
                caller_session=agent_b_session
            )
            
            # Verify response
            assert response["success"] is True
            assert response["status_code"] == 200
            assert response["data"]["message"] == "Hello from OpenAI"
            assert "response_time_ms" in response
            
            # Verify the proxy service was called with correct parameters
            mock_call.assert_called_once()
            call_args = mock_call.call_args
            assert call_args[1]["api_key"] == agent_a_api_key
            assert "api.openai.com" in call_args[1]["target_url"]
        
        # Step 5: Agent A checks logs
        logs = await sage_mcp.list_logs(
            key_id=key_id,
            filters={},
            owner_session=agent_a_session
        )
        
        # Should have logs for key storage, grant creation, and proxy call
        assert len(logs) >= 2  # At least add_key and proxy_call
        
        # Find the proxy call log
        proxy_logs = [log for log in logs if log.get('action') == 'proxy_call']
        assert len(proxy_logs) >= 1
        
        proxy_log = proxy_logs[0]
        assert proxy_log['caller_id'] == agent_b_session
        assert proxy_log['key_id'] == key_id
        assert proxy_log['response_code'] == 200
    
    @pytest.mark.asyncio
    async def test_rate_limiting_workflow(self, sage_mcp):
        """
        Test rate limiting: Agent B hits rate limit after exceeding max_calls_per_day
        """
        # Setup
        agent_a_session = "coral_agent_a_session_789"
        agent_b_session = "coral_agent_b_session_012"
        
        # Agent A stores key
        key_id = await sage_mcp.add_key(
            key_name="test_rate_limit_key",
            api_key="sk-ratelimit123",
            owner_session=agent_a_session
        )
        
        # Agent A grants access with low rate limit
        permissions = {"max_calls_per_day": 2}  # Very low limit for testing
        await sage_mcp.grant_access(
            key_id=key_id,
            caller_id=agent_b_session,
            permissions=permissions,
            expiry=24,
            owner_session=agent_a_session
        )
        
        # Mock successful API responses
        mock_response = {
            "status_code": 200,
            "headers": {},
            "data": {"result": "success"}
        }
        
        with patch.object(sage_mcp.proxy_service, 'make_proxied_call', 
                         return_value=(mock_response, 100.0, 50)):
            
            # First call should succeed
            response1 = await sage_mcp.proxy_call(
                key_id=key_id,
                target_url="https://api.example.com/test",
                payload={"method": "GET"},
                caller_session=agent_b_session
            )
            assert response1["success"] is True
            
            # Second call should succeed
            response2 = await sage_mcp.proxy_call(
                key_id=key_id,
                target_url="https://api.example.com/test",
                payload={"method": "GET"},
                caller_session=agent_b_session
            )
            assert response2["success"] is True
            
            # Third call should fail due to rate limit
            with pytest.raises(RuntimeError) as exc_info:
                await sage_mcp.proxy_call(
                    key_id=key_id,
                    target_url="https://api.example.com/test",
                    payload={"method": "GET"},
                    caller_session=agent_b_session
                )
            
            assert "rate limit exceeded" in str(exc_info.value).lower()
        
        # Check logs show rate limit block
        logs = await sage_mcp.list_logs(
            key_id=key_id,
            filters={"action": "rate_limit_blocked"},
            owner_session=agent_a_session
        )
        
        assert len(logs) >= 1
        rate_limit_log = logs[0]
        assert rate_limit_log['caller_id'] == agent_b_session
        assert rate_limit_log['response_code'] == 429
    
    @pytest.mark.asyncio
    async def test_authorization_failure_workflow(self, sage_mcp):
        """
        Test authorization failure: Agent C tries to use key without grant
        """
        # Setup
        agent_a_session = "coral_agent_a_session_345"
        agent_c_session = "coral_agent_c_session_678"  # No grant
        
        # Agent A stores key
        key_id = await sage_mcp.add_key(
            key_name="test_auth_key",
            api_key="sk-auth123",
            owner_session=agent_a_session
        )
        
        # Agent C tries to make proxy call without grant
        with pytest.raises(RuntimeError) as exc_info:
            await sage_mcp.proxy_call(
                key_id=key_id,
                target_url="https://api.example.com/unauthorized",
                payload={"method": "GET"},
                caller_session=agent_c_session
            )
        
        assert "access denied" in str(exc_info.value).lower()
        
        # Check logs show authorization failure
        logs = await sage_mcp.list_logs(
            key_id=key_id,
            filters={"action": "authorization_failed"},
            owner_session=agent_a_session
        )
        
        assert len(logs) >= 1
        auth_fail_log = logs[0]
        assert auth_fail_log['caller_id'] == agent_c_session
        assert auth_fail_log['response_code'] == 403
    
    @pytest.mark.asyncio
    async def test_key_revocation_workflow(self, sage_mcp):
        """
        Test key revocation: Agent A revokes key, Agent B can no longer use it
        """
        # Setup
        agent_a_session = "coral_agent_a_session_999"
        agent_b_session = "coral_agent_b_session_888"
        
        # Agent A stores key and grants access to Agent B
        key_id = await sage_mcp.add_key(
            key_name="test_revoke_key",
            api_key="sk-revoke123",
            owner_session=agent_a_session
        )
        
        permissions = {"max_calls_per_day": 100}
        await sage_mcp.grant_access(
            key_id=key_id,
            caller_id=agent_b_session,
            permissions=permissions,
            expiry=24,
            owner_session=agent_a_session
        )
        
        # Agent B makes successful call initially
        mock_response = {
            "status_code": 200,
            "headers": {},
            "data": {"result": "success"}
        }
        
        with patch.object(sage_mcp.proxy_service, 'make_proxied_call', 
                         return_value=(mock_response, 100.0, 50)):
            
            response = await sage_mcp.proxy_call(
                key_id=key_id,
                target_url="https://api.example.com/test",
                payload={"method": "GET"},
                caller_session=agent_b_session
            )
            assert response["success"] is True
        
        # Agent A revokes the key
        revoke_success = await sage_mcp.revoke_key(key_id, agent_a_session)
        assert revoke_success is True
        
        # Agent B can no longer use the key
        with pytest.raises(RuntimeError) as exc_info:
            await sage_mcp.proxy_call(
                key_id=key_id,
                target_url="https://api.example.com/test",
                payload={"method": "GET"},
                caller_session=agent_b_session
            )
        
        assert "access denied" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_grant_expiration_workflow(self, sage_mcp):
        """
        Test grant expiration: Grant expires and Agent B loses access
        """
        # Setup
        agent_a_session = "coral_agent_a_session_111"
        agent_b_session = "coral_agent_b_session_222"
        
        # Agent A stores key
        key_id = await sage_mcp.add_key(
            key_name="test_expire_key",
            api_key="sk-expire123",
            owner_session=agent_a_session
        )
        
        # Create grant with very short expiry (using internal method for testing)
        permissions = {"max_calls_per_day": 100}
        expires_at = datetime.utcnow() + timedelta(seconds=1)  # 1 second expiry
        
        # Use authorization engine directly to create expired grant
        await sage_mcp.authorization_engine.create_grant(
            key_id=key_id,
            caller_id=agent_b_session,
            permissions=permissions,
            expires_at=expires_at,
            owner_id=agent_a_session,
            _allow_past_expiry=True
        )
        
        # Wait for grant to expire
        await asyncio.sleep(2)
        
        # Agent B should not be able to make calls
        with pytest.raises(RuntimeError) as exc_info:
            await sage_mcp.proxy_call(
                key_id=key_id,
                target_url="https://api.example.com/test",
                payload={"method": "GET"},
                caller_session=agent_b_session
            )
        
        assert "access denied" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_error_handling_and_logging(self, sage_mcp):
        """
        Test comprehensive error handling and privacy-aware logging
        """
        # Setup
        agent_a_session = "coral_agent_a_session_error"
        agent_b_session = "coral_agent_b_session_error"
        
        # Test invalid session validation
        with pytest.raises(ValueError):
            await sage_mcp.add_key("test", "sk-123", "invalid_session")
        
        # Test key storage with valid session
        key_id = await sage_mcp.add_key(
            key_name="error_test_key",
            api_key="sk-error123",
            owner_session=agent_a_session
        )
        
        # Test grant with invalid permissions
        with pytest.raises(ValueError):
            await sage_mcp.grant_access(
                key_id=key_id,
                caller_id=agent_b_session,
                permissions={},  # Missing max_calls_per_day
                expiry=24,
                owner_session=agent_a_session
            )
        
        # Test proxy call with invalid URL
        permissions = {"max_calls_per_day": 10}
        await sage_mcp.grant_access(
            key_id=key_id,
            caller_id=agent_b_session,
            permissions=permissions,
            expiry=24,
            owner_session=agent_a_session
        )
        
        # Mock proxy service to raise an exception
        with patch.object(sage_mcp.proxy_service, 'make_proxied_call', 
                         side_effect=Exception("Network error")):
            
            with pytest.raises(RuntimeError) as exc_info:
                await sage_mcp.proxy_call(
                    key_id=key_id,
                    target_url="https://api.example.com/error",
                    payload={"method": "GET"},
                    caller_session=agent_b_session
                )
            
            assert "proxy call failed" in str(exc_info.value).lower()
        
        # Verify error was logged
        logs = await sage_mcp.list_logs(
            key_id=key_id,
            filters={},
            owner_session=agent_a_session
        )
        
        # Should have error logs
        error_logs = [log for log in logs if log.get('error_message') is not None]
        assert len(error_logs) >= 1
    
    @pytest.mark.asyncio
    async def test_mcp_protocol_integration(self, sage_mcp):
        """
        Test MCP protocol request handling
        """
        # Test add_key via MCP protocol
        add_key_request = {
            "method": "add_key",
            "session_id": "coral_mcp_test_session",
            "params": {
                "key_name": "mcp_test_key",
                "api_key": "sk-mcp123"
            }
        }
        
        response = await sage_mcp.handle_mcp_request(add_key_request)
        
        assert response["success"] is True
        assert "key_id" in response["data"]
        key_id = response["data"]["key_id"]
        
        # Test grant_access via MCP protocol
        grant_request = {
            "method": "grant_access",
            "session_id": "coral_mcp_test_session",
            "params": {
                "key_id": key_id,
                "caller_id": "coral_mcp_caller_session",
                "permissions": {"max_calls_per_day": 5},
                "expiry_hours": 12
            }
        }
        
        response = await sage_mcp.handle_mcp_request(grant_request)
        assert response["success"] is True
        
        # Test proxy_call via MCP protocol
        with patch.object(sage_mcp.proxy_service, 'make_proxied_call', 
                         return_value=({"status_code": 200, "data": {}}, 100.0, 50)):
            
            proxy_request = {
                "method": "proxy_call",
                "session_id": "coral_mcp_caller_session",
                "params": {
                    "key_id": key_id,
                    "target_url": "https://api.example.com/mcp",
                    "method": "GET"
                }
            }
            
            response = await sage_mcp.handle_mcp_request(proxy_request)
            assert response["success"] is True
            assert response["data"]["status_code"] == 200
        
        # Test list_logs via MCP protocol
        logs_request = {
            "method": "list_logs",
            "session_id": "coral_mcp_test_session",
            "params": {
                "key_id": key_id,
                "filters": {}
            }
        }
        
        response = await sage_mcp.handle_mcp_request(logs_request)
        assert response["success"] is True
        assert "logs" in response["data"]
        assert len(response["data"]["logs"]) >= 1
    
    @pytest.mark.asyncio
    async def test_usage_statistics_and_cleanup(self, sage_mcp):
        """
        Test usage statistics and cleanup operations
        """
        # Setup
        agent_a_session = "coral_agent_a_stats"
        agent_b_session = "coral_agent_b_stats"
        
        # Create key and grant
        key_id = await sage_mcp.add_key(
            key_name="stats_test_key",
            api_key="sk-stats123",
            owner_session=agent_a_session
        )
        
        permissions = {"max_calls_per_day": 100}
        await sage_mcp.grant_access(
            key_id=key_id,
            caller_id=agent_b_session,
            permissions=permissions,
            expiry=24,
            owner_session=agent_a_session
        )
        
        # Make some proxy calls
        mock_response = {"status_code": 200, "data": {}}
        with patch.object(sage_mcp.proxy_service, 'make_proxied_call', 
                         return_value=(mock_response, 150.0, 100)):
            
            for i in range(3):
                await sage_mcp.proxy_call(
                    key_id=key_id,
                    target_url="https://api.example.com/stats",
                    payload={"method": "GET"},
                    caller_session=agent_b_session
                )
        
        # Get usage statistics
        stats = await sage_mcp.get_usage_stats(
            key_id=key_id,
            owner_session=agent_a_session,
            days=7
        )
        
        assert stats["key_id"] == key_id
        assert stats["total_calls"] >= 3
        assert stats["successful_calls"] >= 3
        assert stats["unique_callers"] >= 1
        
        # Test cleanup operations
        cleanup_count = await sage_mcp.cleanup_expired_grants()
        assert isinstance(cleanup_count, int)
        assert cleanup_count >= 0
        
        # Test list keys
        keys = await sage_mcp.list_keys(agent_a_session)
        assert len(keys) >= 1
        assert any(key["key_id"] == key_id for key in keys)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])