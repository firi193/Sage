"""
HTTP Proxy Service for Sage - handles external API calls with key injection
"""

import aiohttp
import asyncio
import json
import logging
import time
from typing import Dict, Any, Optional, Tuple
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class ProxyService:
    """
    HTTP client for external API calls with key injection and performance tracking
    """
    
    def __init__(self, timeout: int = 30):
        """
        Initialize proxy service
        
        Args:
            timeout: Request timeout in seconds
        """
        self.timeout = timeout
        self._session = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session"""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session
    
    async def close(self):
        """Close HTTP session"""
        if self._session and not self._session.closed:
            await self._session.close()
    
    async def make_proxied_call(self, target_url: str, method: str, headers: Optional[Dict[str, str]] = None,
                               body: Optional[Dict[str, Any]] = None, api_key: str = None) -> Tuple[Dict[str, Any], float, int]:
        """
        Make a proxied HTTP call with key injection and performance tracking
        
        Args:
            target_url: Target API URL
            method: HTTP method (GET, POST, etc.)
            headers: Request headers
            body: Request body
            api_key: API key to inject
            
        Returns:
            Tuple of (response_data, response_time_ms, payload_size)
            
        Raises:
            ValueError: If URL is invalid
            aiohttp.ClientError: If request fails
        """
        start_time = time.time()
        
        # Validate URL
        parsed_url = urlparse(target_url)
        if not parsed_url.scheme or not parsed_url.netloc:
            raise ValueError(f"Invalid URL: {target_url}")
        
        # Prepare headers
        request_headers = headers.copy() if headers else {}
        
        # Inject API key based on common patterns
        if api_key:
            request_headers = self.inject_api_key(request_headers, api_key, target_url)
        
        # Calculate payload size
        payload_size = 0
        request_body = None
        if body:
            if method.upper() in ['POST', 'PUT', 'PATCH']:
                request_body = json.dumps(body) if isinstance(body, dict) else str(body)
                payload_size = len(request_body.encode('utf-8'))
                if 'content-type' not in [h.lower() for h in request_headers.keys()]:
                    request_headers['Content-Type'] = 'application/json'
        
        session = await self._get_session()
        
        try:
            logger.info(f"Making proxied call to {target_url} with method {method}")
            
            async with session.request(
                method=method.upper(),
                url=target_url,
                headers=request_headers,
                data=request_body
            ) as response:
                response_time = (time.time() - start_time) * 1000  # Convert to milliseconds
                
                # Read response
                response_text = await response.text()
                
                try:
                    response_data = json.loads(response_text) if response_text else {}
                except json.JSONDecodeError:
                    response_data = {"raw_response": response_text}
                
                # Add response metadata
                result = {
                    "status_code": response.status,
                    "headers": dict(response.headers),
                    "data": response_data
                }
                
                logger.info(f"Proxied call completed: {response.status} in {response_time:.2f}ms")
                
                return result, response_time, payload_size
                
        except asyncio.TimeoutError:
            response_time = (time.time() - start_time) * 1000
            logger.error(f"Proxied call timed out after {response_time:.2f}ms")
            raise aiohttp.ClientError(f"Request timed out after {self.timeout}s")
        
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            logger.error(f"Proxied call failed after {response_time:.2f}ms: {e}")
            raise
    
    def inject_api_key(self, headers: Dict[str, str], api_key: str, target_url: str) -> Dict[str, str]:
        """
        Inject API key into request headers based on common patterns
        
        Args:
            headers: Existing request headers
            api_key: API key to inject
            target_url: Target URL (used to determine injection method)
            
        Returns:
            Updated headers with API key injected
        """
        headers = headers.copy()
        
        # Common API key injection patterns
        domain = urlparse(target_url).netloc.lower()
        
        if 'openai.com' in domain or 'api.openai.com' in domain:
            headers['Authorization'] = f'Bearer {api_key}'
        elif 'anthropic.com' in domain:
            headers['x-api-key'] = api_key
        elif 'googleapis.com' in domain:
            headers['Authorization'] = f'Bearer {api_key}'
        elif 'api.github.com' in domain:
            headers['Authorization'] = f'token {api_key}'
        elif 'api.stripe.com' in domain:
            headers['Authorization'] = f'Bearer {api_key}'
        else:
            # Default patterns - try common header names
            if not any(h.lower() in ['authorization', 'x-api-key', 'api-key'] for h in headers.keys()):
                # Default to Authorization Bearer
                headers['Authorization'] = f'Bearer {api_key}'
        
        return headers
    
    def measure_performance(self, start_time: float, payload_size: int) -> Dict[str, Any]:
        """
        Measure and return performance metrics
        
        Args:
            start_time: Request start time
            payload_size: Request payload size in bytes
            
        Returns:
            Performance metrics dictionary
        """
        response_time = (time.time() - start_time) * 1000  # Convert to milliseconds
        
        return {
            "response_time_ms": response_time,
            "payload_size_bytes": payload_size,
            "timestamp": time.time()
        }