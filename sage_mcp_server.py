#!/usr/bin/env python3
"""
Sage MCP Server - Model Context Protocol server for secure API key management

This server exposes Sage functionality as MCP tools that Coral agents can use.
Coral agents connect to this server to securely manage and use API keys.

Usage:
    python sage_mcp_server.py

The server will start and listen for MCP connections from Coral agents.
"""

import asyncio
import json
import logging
import sys
from typing import Any, Dict, List, Optional, Sequence
from contextlib import asynccontextmanager

# MCP server imports
from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.types import (
    CallToolRequest,
    CallToolResult,
    ListToolsRequest,
    TextContent,
    Tool,
    INVALID_PARAMS,
    INTERNAL_ERROR
)

# Sage imports
from sage.sage_mcp import SageMCP


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("sage-mcp-server")


class SageMCPServer:
    """MCP Server wrapper for Sage functionality"""
    
    def __init__(self):
        self.sage = SageMCP()
        self.server = Server("sage-mcp-server")
        self._setup_tools()
    
    def _setup_tools(self):
        """Register MCP tools with the server"""
        
        # Tool 1: Store API Key
        @self.server.list_tools()
        async def list_tools() -> List[Tool]:
            """List available tools"""
            return [
                Tool(
                    name="store_api_key",
                    description="Securely store an API key with encryption",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "key_name": {
                                "type": "string",
                                "description": "Human-readable name for the API key"
                            },
                            "api_key": {
                                "type": "string",
                                "description": "The API key to store securely"
                            },
                            "owner_session": {
                                "type": "string",
                                "description": "Coral session ID of the key owner"
                            }
                        },
                        "required": ["key_name", "api_key", "owner_session"]
                    }
                ),
                Tool(
                    name="grant_key_access",
                    description="Grant another agent access to use your API key",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "key_id": {
                                "type": "string",
                                "description": "ID of the key to grant access to"
                            },
                            "caller_id": {
                                "type": "string",
                                "description": "Coral session ID of the agent to grant access to"
                            },
                            "max_calls_per_day": {
                                "type": "integer",
                                "description": "Maximum number of API calls per day",
                                "minimum": 1,
                                "maximum": 10000
                            },
                            "expiry_hours": {
                                "type": "integer",
                                "description": "Hours until the grant expires",
                                "minimum": 1,
                                "maximum": 8760
                            },
                            "owner_session": {
                                "type": "string",
                                "description": "Coral session ID of the key owner"
                            }
                        },
                        "required": ["key_id", "caller_id", "max_calls_per_day", "expiry_hours", "owner_session"]
                    }
                ),
                Tool(
                    name="proxy_api_call",
                    description="Make an API call using a shared key with rate limiting and audit logging",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "key_id": {
                                "type": "string",
                                "description": "ID of the key to use for the API call"
                            },
                            "target_url": {
                                "type": "string",
                                "description": "Target API URL to call"
                            },
                            "method": {
                                "type": "string",
                                "description": "HTTP method (GET, POST, PUT, DELETE, etc.)",
                                "enum": ["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"]
                            },
                            "headers": {
                                "type": "object",
                                "description": "HTTP headers to include (API key will be injected automatically)",
                                "additionalProperties": {"type": "string"}
                            },
                            "body": {
                                "type": "object",
                                "description": "Request body for POST/PUT requests"
                            },
                            "caller_session": {
                                "type": "string",
                                "description": "Coral session ID of the calling agent"
                            }
                        },
                        "required": ["key_id", "target_url", "caller_session"]
                    }
                ),
                Tool(
                    name="list_my_keys",
                    description="List all API keys you own (metadata only, no actual keys)",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "owner_session": {
                                "type": "string",
                                "description": "Coral session ID of the key owner"
                            }
                        },
                        "required": ["owner_session"]
                    }
                ),
                Tool(
                    name="view_audit_logs",
                    description="View audit logs for your API keys",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "key_id": {
                                "type": "string",
                                "description": "ID of the key to view logs for"
                            },
                            "owner_session": {
                                "type": "string",
                                "description": "Coral session ID of the key owner"
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of log entries to return",
                                "minimum": 1,
                                "maximum": 1000,
                                "default": 50
                            },
                            "caller_id": {
                                "type": "string",
                                "description": "Filter logs by specific caller (optional)"
                            },
                            "action": {
                                "type": "string",
                                "description": "Filter logs by action type (optional)",
                                "enum": ["proxy_call", "grant_access", "rate_limit_blocked", "authorization_failed"]
                            }
                        },
                        "required": ["key_id", "owner_session"]
                    }
                ),
                Tool(
                    name="get_usage_statistics",
                    description="Get usage statistics for your API keys",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "key_id": {
                                "type": "string",
                                "description": "ID of the key to get statistics for"
                            },
                            "owner_session": {
                                "type": "string",
                                "description": "Coral session ID of the key owner"
                            },
                            "days": {
                                "type": "integer",
                                "description": "Number of days to include in statistics",
                                "minimum": 1,
                                "maximum": 365,
                                "default": 7
                            }
                        },
                        "required": ["key_id", "owner_session"]
                    }
                ),
                Tool(
                    name="revoke_api_key",
                    description="Revoke an API key and all associated grants",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "key_id": {
                                "type": "string",
                                "description": "ID of the key to revoke"
                            },
                            "owner_session": {
                                "type": "string",
                                "description": "Coral session ID of the key owner"
                            }
                        },
                        "required": ["key_id", "owner_session"]
                    }
                )
            ]
        
        # Tool implementations
        @self.server.call_tool()
        async def call_tool(name: str, arguments: Dict[str, Any]) -> CallToolResult:
            """Handle tool calls from Coral agents"""
            
            try:
                if name == "store_api_key":
                    return await self._handle_store_api_key(arguments)
                elif name == "grant_key_access":
                    return await self._handle_grant_key_access(arguments)
                elif name == "proxy_api_call":
                    return await self._handle_proxy_api_call(arguments)
                elif name == "list_my_keys":
                    return await self._handle_list_my_keys(arguments)
                elif name == "view_audit_logs":
                    return await self._handle_view_audit_logs(arguments)
                elif name == "get_usage_statistics":
                    return await self._handle_get_usage_statistics(arguments)
                elif name == "revoke_api_key":
                    return await self._handle_revoke_api_key(arguments)
                else:
                    return CallToolResult(
                        content=[TextContent(
                            type="text",
                            text=f"Unknown tool: {name}"
                        )],
                        isError=True
                    )
                    
            except Exception as e:
                logger.error(f"Error in tool {name}: {e}")
                return CallToolResult(
                    content=[TextContent(
                        type="text",
                        text=f"Error executing {name}: {str(e)}"
                    )],
                    isError=True
                )
    
    async def _handle_store_api_key(self, args: Dict[str, Any]) -> CallToolResult:
        """Handle store_api_key tool call"""
        try:
            key_id = await self.sage.add_key(
                key_name=args["key_name"],
                api_key=args["api_key"],
                owner_session=args["owner_session"]
            )
            
            result = {
                "success": True,
                "key_id": key_id,
                "message": f"API key '{args['key_name']}' stored successfully"
            }
            
            return CallToolResult(
                content=[TextContent(
                    type="text",
                    text=json.dumps(result, indent=2)
                )]
            )
            
        except Exception as e:
            return CallToolResult(
                content=[TextContent(
                    type="text",
                    text=json.dumps({
                        "success": False,
                        "error": str(e)
                    }, indent=2)
                )],
                isError=True
            )
    
    async def _handle_grant_key_access(self, args: Dict[str, Any]) -> CallToolResult:
        """Handle grant_key_access tool call"""
        try:
            permissions = {"max_calls_per_day": args["max_calls_per_day"]}
            
            success = await self.sage.grant_access(
                key_id=args["key_id"],
                caller_id=args["caller_id"],
                permissions=permissions,
                expiry=args["expiry_hours"],
                owner_session=args["owner_session"]
            )
            
            result = {
                "success": success,
                "message": f"Access granted to {args['caller_id']}" if success else "Failed to grant access"
            }
            
            return CallToolResult(
                content=[TextContent(
                    type="text",
                    text=json.dumps(result, indent=2)
                )]
            )
            
        except Exception as e:
            return CallToolResult(
                content=[TextContent(
                    type="text",
                    text=json.dumps({
                        "success": False,
                        "error": str(e)
                    }, indent=2)
                )],
                isError=True
            )
    
    async def _handle_proxy_api_call(self, args: Dict[str, Any]) -> CallToolResult:
        """Handle proxy_api_call tool call"""
        try:
            payload = {
                "method": args.get("method", "GET"),
                "headers": args.get("headers", {}),
                "body": args.get("body", {})
            }
            
            response = await self.sage.proxy_call(
                key_id=args["key_id"],
                target_url=args["target_url"],
                payload=payload,
                caller_session=args["caller_session"]
            )
            
            return CallToolResult(
                content=[TextContent(
                    type="text",
                    text=json.dumps(response, indent=2)
                )]
            )
            
        except Exception as e:
            return CallToolResult(
                content=[TextContent(
                    type="text",
                    text=json.dumps({
                        "success": False,
                        "error": str(e)
                    }, indent=2)
                )],
                isError=True
            )
    
    async def _handle_list_my_keys(self, args: Dict[str, Any]) -> CallToolResult:
        """Handle list_my_keys tool call"""
        try:
            keys = await self.sage.list_keys(args["owner_session"])
            
            result = {
                "success": True,
                "keys": keys,
                "count": len(keys)
            }
            
            return CallToolResult(
                content=[TextContent(
                    type="text",
                    text=json.dumps(result, indent=2)
                )]
            )
            
        except Exception as e:
            return CallToolResult(
                content=[TextContent(
                    type="text",
                    text=json.dumps({
                        "success": False,
                        "error": str(e)
                    }, indent=2)
                )],
                isError=True
            )
    
    async def _handle_view_audit_logs(self, args: Dict[str, Any]) -> CallToolResult:
        """Handle view_audit_logs tool call"""
        try:
            filters = {
                "limit": args.get("limit", 50)
            }
            
            if "caller_id" in args:
                filters["caller_id"] = args["caller_id"]
            if "action" in args:
                filters["action"] = args["action"]
            
            logs = await self.sage.list_logs(
                key_id=args["key_id"],
                filters=filters,
                owner_session=args["owner_session"]
            )
            
            result = {
                "success": True,
                "logs": logs,
                "count": len(logs)
            }
            
            return CallToolResult(
                content=[TextContent(
                    type="text",
                    text=json.dumps(result, indent=2)
                )]
            )
            
        except Exception as e:
            return CallToolResult(
                content=[TextContent(
                    type="text",
                    text=json.dumps({
                        "success": False,
                        "error": str(e)
                    }, indent=2)
                )],
                isError=True
            )
    
    async def _handle_get_usage_statistics(self, args: Dict[str, Any]) -> CallToolResult:
        """Handle get_usage_statistics tool call"""
        try:
            stats = await self.sage.get_usage_stats(
                key_id=args["key_id"],
                owner_session=args["owner_session"],
                days=args.get("days", 7)
            )
            
            result = {
                "success": True,
                "statistics": stats
            }
            
            return CallToolResult(
                content=[TextContent(
                    type="text",
                    text=json.dumps(result, indent=2)
                )]
            )
            
        except Exception as e:
            return CallToolResult(
                content=[TextContent(
                    type="text",
                    text=json.dumps({
                        "success": False,
                        "error": str(e)
                    }, indent=2)
                )],
                isError=True
            )
    
    async def _handle_revoke_api_key(self, args: Dict[str, Any]) -> CallToolResult:
        """Handle revoke_api_key tool call"""
        try:
            success = await self.sage.revoke_key(
                key_id=args["key_id"],
                owner_session=args["owner_session"]
            )
            
            result = {
                "success": success,
                "message": "API key revoked successfully" if success else "Failed to revoke key"
            }
            
            return CallToolResult(
                content=[TextContent(
                    type="text",
                    text=json.dumps(result, indent=2)
                )]
            )
            
        except Exception as e:
            return CallToolResult(
                content=[TextContent(
                    type="text",
                    text=json.dumps({
                        "success": False,
                        "error": str(e)
                    }, indent=2)
                )],
                isError=True
            )
    
    async def cleanup(self):
        """Cleanup resources"""
        await self.sage.close()


async def main():
    """Main server function"""
    logger.info("Starting Sage MCP Server...")
    
    sage_server = SageMCPServer()
    
    try:
        # Run the MCP server using stdio transport
        async with stdio_server() as (read_stream, write_stream):
            logger.info("Sage MCP Server is running and ready for connections")
            await sage_server.server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name="sage-mcp-server",
                    server_version="1.0.0",
                    capabilities=sage_server.server.get_capabilities(
                        notification_options=None,
                        experimental_capabilities={}
                    )
                )
            )
    except KeyboardInterrupt:
        logger.info("Server interrupted by user")
    except Exception as e:
        logger.error(f"Server error: {e}")
    finally:
        logger.info("Shutting down Sage MCP Server...")
        await sage_server.cleanup()


if __name__ == "__main__":
    asyncio.run(main())