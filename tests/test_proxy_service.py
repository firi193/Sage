"""
Unit tests for ProxyService
"""

import pytest
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
import aiohttp

from sage.services.proxy_service import ProxyService


class TestProxyService:
    
    @pytest.fixture
    def proxy_service(self):
        return ProxyService(timeout=10)
    
    @pytest.fixture
    def mock_response(self):
        """Create a mock aiohttp response"""
        response = MagicMock()
        response.status = 200
        response.headers = {"content-type": "application/json"}
        response.text = AsyncMock(return_value='{"result": "success"}')
        return response
    
    @pytest.mark.asyncio
    async def test_inject_api_key_openai(self, proxy_service):
        """Test API key injection for OpenAI"""
        headers = {}
        api_key = "sk-test123"
        target_url = "https://api.openai.com/v1/chat/completions"
        
        result = proxy_service.inject_api_key(headers, api_key, target_url)
        
        assert result["Authorization"] == "Bearer sk-test123"
    
    @pytest.mark.asyncio
    async def test_inject_api_key_anthropic(self, proxy_service):
        """Test API key injection for Anthropic"""
        headers = {}
        api_key = "sk-ant-test123"
        target_url = "https://api.anthropic.com/v1/messages"
        
        result = proxy_service.inject_api_key(headers, api_key, target_url)
        
        assert result["x-api-key"] == "sk-ant-test123"
    
    @pytest.mark.asyncio
    async def test_inject_api_key_github(self, proxy_service):
        """Test API key injection for GitHub"""
        headers = {}
        api_key = "ghp_test123"
        target_url = "https://api.github.com/user"
        
        result = proxy_service.inject_api_key(headers, api_key, target_url)
        
        assert result["Authorization"] == "token ghp_test123"
    
    @pytest.mark.asyncio
    async def test_inject_api_key_default(self, proxy_service):
        """Test default API key injection"""
        headers = {}
        api_key = "test123"
        target_url = "https://api.example.com/data"
        
        result = proxy_service.inject_api_key(headers, api_key, target_url)
        
        assert result["Authorization"] == "Bearer test123"
    
    @pytest.mark.asyncio
    async def test_inject_api_key_preserves_existing(self, proxy_service):
        """Test that existing headers are preserved"""
        headers = {"User-Agent": "TestAgent", "Content-Type": "application/json"}
        api_key = "test123"
        target_url = "https://api.example.com/data"
        
        result = proxy_service.inject_api_key(headers, api_key, target_url)
        
        assert result["User-Agent"] == "TestAgent"
        assert result["Content-Type"] == "application/json"
        assert result["Authorization"] == "Bearer test123"
    
    @pytest.mark.asyncio
    async def test_make_proxied_call_success(self, proxy_service, mock_response):
        """Test successful proxied call"""
        with patch('aiohttp.ClientSession.request') as mock_request:
            # Add a small delay to ensure measurable response time
            async def mock_request_with_delay(*args, **kwargs):
                await asyncio.sleep(0.001)  # 1ms delay
                return mock_response
            
            mock_request.return_value.__aenter__ = mock_request_with_delay
            
            result, response_time, payload_size = await proxy_service.make_proxied_call(
                target_url="https://api.example.com/data",
                method="GET",
                headers={"User-Agent": "TestAgent"},
                api_key="test123"
            )
            
            assert result["status_code"] == 200
            assert result["data"] == {"result": "success"}
            assert response_time >= 0  # Allow for 0 or positive response time
            assert payload_size == 0  # GET request has no body
    
    @pytest.mark.asyncio
    async def test_make_proxied_call_with_body(self, proxy_service, mock_response):
        """Test proxied call with request body"""
        with patch('aiohttp.ClientSession.request') as mock_request:
            mock_request.return_value.__aenter__.return_value = mock_response
            
            body = {"message": "Hello, world!"}
            result, response_time, payload_size = await proxy_service.make_proxied_call(
                target_url="https://api.example.com/data",
                method="POST",
                body=body,
                api_key="test123"
            )
            
            assert result["status_code"] == 200
            assert payload_size > 0  # POST request has body
            
            # Verify the request was made with correct parameters
            mock_request.assert_called_once()
            call_args = mock_request.call_args
            assert call_args[1]["method"] == "POST"
            assert call_args[1]["url"] == "https://api.example.com/data"
            assert "Authorization" in call_args[1]["headers"]
    
    @pytest.mark.asyncio
    async def test_make_proxied_call_invalid_url(self, proxy_service):
        """Test proxied call with invalid URL"""
        with pytest.raises(ValueError, match="Invalid URL"):
            await proxy_service.make_proxied_call(
                target_url="not-a-url",
                method="GET",
                api_key="test123"
            )
    
    @pytest.mark.asyncio
    async def test_make_proxied_call_timeout(self, proxy_service):
        """Test proxied call timeout"""
        with patch('aiohttp.ClientSession.request') as mock_request:
            mock_request.side_effect = asyncio.TimeoutError()
            
            with pytest.raises(aiohttp.ClientError, match="Request timed out"):
                await proxy_service.make_proxied_call(
                    target_url="https://api.example.com/data",
                    method="GET",
                    api_key="test123"
                )
    
    @pytest.mark.asyncio
    async def test_make_proxied_call_non_json_response(self, proxy_service):
        """Test proxied call with non-JSON response"""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.headers = {"content-type": "text/plain"}
        mock_response.text = AsyncMock(return_value="Plain text response")
        
        with patch('aiohttp.ClientSession.request') as mock_request:
            mock_request.return_value.__aenter__.return_value = mock_response
            
            result, response_time, payload_size = await proxy_service.make_proxied_call(
                target_url="https://api.example.com/data",
                method="GET",
                api_key="test123"
            )
            
            assert result["status_code"] == 200
            assert result["data"] == {"raw_response": "Plain text response"}
    
    @pytest.mark.asyncio
    async def test_measure_performance(self, proxy_service):
        """Test performance measurement"""
        import time
        start_time = time.time()
        payload_size = 1024
        
        # Wait a small amount to ensure measurable time difference
        await asyncio.sleep(0.01)
        
        metrics = proxy_service.measure_performance(start_time, payload_size)
        
        assert metrics["response_time_ms"] > 0
        assert metrics["payload_size_bytes"] == 1024
        assert "timestamp" in metrics
    
    @pytest.mark.asyncio
    async def test_session_management(self, proxy_service):
        """Test HTTP session management"""
        # Initially no session
        assert proxy_service._session is None
        
        # Get session creates one
        session = await proxy_service._get_session()
        assert session is not None
        assert proxy_service._session is session
        
        # Getting again returns same session
        session2 = await proxy_service._get_session()
        assert session2 is session
        
        # Close session
        await proxy_service.close()
        assert proxy_service._session.closed
    
    @pytest.mark.asyncio
    async def test_close_no_session(self, proxy_service):
        """Test closing when no session exists"""
        # Should not raise an error
        await proxy_service.close()
        assert proxy_service._session is None