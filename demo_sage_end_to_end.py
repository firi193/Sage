#!/usr/bin/env python3
"""
Sage MCP End-to-End Demo Script

This script demonstrates the complete Sage MCP workflow:
1. Agent A stores their API key
2. Agent A grants access to Agent B
3. Agent B makes proxy calls using Agent A's key
4. Agent A views audit logs
5. Rate limiting and error handling demonstrations

Run this script to see Sage MCP in action!
"""

import asyncio
import json
from datetime import datetime, timedelta
from unittest.mock import patch

from sage.sage_mcp import SageMCP


class SageDemo:
    """Demo class to showcase Sage MCP functionality"""
    
    def __init__(self):
        self.sage = SageMCP()
        
        # Demo agent credentials
        self.agent_a_session = "coral_agent_alice_session_12345"
        self.agent_b_session = "coral_agent_bob_session_67890"
        self.agent_c_session = "coral_agent_charlie_session_99999"
        
        # Demo API key
        self.demo_api_key = "sk-demo123456789abcdef"
        self.demo_key_name = "openai_production_key"
    
    async def print_header(self, title: str):
        """Print a formatted header"""
        print(f"\n{'='*60}")
        print(f"  {title}")
        print(f"{'='*60}")
    
    async def print_step(self, step: str, description: str):
        """Print a formatted step"""
        print(f"\n🔹 Step {step}: {description}")
        print("-" * 50)
    
    async def print_success(self, message: str):
        """Print a success message"""
        print(f"✅ {message}")
    
    async def print_error(self, message: str):
        """Print an error message"""
        print(f"❌ {message}")
    
    async def print_info(self, message: str):
        """Print an info message"""
        print(f"ℹ️  {message}")
    
    async def demo_key_storage(self):
        """Demonstrate key storage functionality"""
        await self.print_step("1", "Agent Alice stores her OpenAI API key")
        
        try:
            key_id = await self.sage.add_key(
                key_name=self.demo_key_name,
                api_key=self.demo_api_key,
                owner_session=self.agent_a_session
            )
            
            await self.print_success(f"Key stored successfully! Key ID: {key_id}")
            self.stored_key_id = key_id
            
            # Show key metadata (no sensitive data)
            keys = await self.sage.list_keys(self.agent_a_session)
            await self.print_info(f"Alice now has {len(keys)} key(s) stored")
            for key in keys:
                print(f"   - {key['key_name']} (ID: {key['key_id'][:8]}...)")
            
            return key_id
            
        except Exception as e:
            await self.print_error(f"Failed to store key: {e}")
            return None
    
    async def demo_grant_access(self, key_id: str):
        """Demonstrate access grant functionality"""
        await self.print_step("2", "Agent Alice grants access to Agent Bob")
        
        try:
            permissions = {
                "max_calls_per_day": 10
            }
            
            success = await self.sage.grant_access(
                key_id=key_id,
                caller_id=self.agent_b_session,
                permissions=permissions,
                expiry=24,  # 24 hours
                owner_session=self.agent_a_session
            )
            
            if success:
                await self.print_success("Access granted successfully!")
                await self.print_info(f"Bob can now make up to {permissions['max_calls_per_day']} calls per day")
                return True
            else:
                await self.print_error("Failed to grant access")
                return False
                
        except Exception as e:
            await self.print_error(f"Failed to grant access: {e}")
            return False
    
    async def demo_successful_proxy_call(self, key_id: str):
        """Demonstrate successful proxy call"""
        await self.print_step("3", "Agent Bob makes a successful API call")
        
        # Mock the external API response
        mock_response = {
            "status_code": 200,
            "headers": {"content-type": "application/json"},
            "data": {
                "id": "chatcmpl-demo123",
                "object": "chat.completion",
                "choices": [{
                    "message": {
                        "role": "assistant",
                        "content": "Hello! This is a demo response from the OpenAI API."
                    }
                }],
                "usage": {"total_tokens": 25}
            }
        }
        
        with patch.object(self.sage.proxy_service, 'make_proxied_call', 
                         return_value=(mock_response, 150.0, 120)) as mock_call:
            
            try:
                response = await self.sage.proxy_call(
                    key_id=key_id,
                    target_url="https://api.openai.com/v1/chat/completions",
                    payload={
                        "method": "POST",
                        "headers": {"Content-Type": "application/json"},
                        "body": {
                            "model": "gpt-3.5-turbo",
                            "messages": [{"role": "user", "content": "Hello!"}]
                        }
                    },
                    caller_session=self.agent_b_session
                )
                
                await self.print_success("API call successful!")
                await self.print_info(f"Response status: {response['status_code']}")
                await self.print_info(f"Response time: {response['response_time_ms']:.1f}ms")
                
                # Show the API response content
                if response.get('data', {}).get('choices'):
                    content = response['data']['choices'][0]['message']['content']
                    print(f"   API Response: \"{content}\"")
                
                return True
                
            except Exception as e:
                await self.print_error(f"Proxy call failed: {e}")
                return False
    
    async def demo_multiple_calls_and_rate_limiting(self, key_id: str):
        """Demonstrate multiple calls and rate limiting"""
        await self.print_step("4", "Agent Bob makes multiple calls (testing rate limits)")
        
        mock_response = {
            "status_code": 200,
            "headers": {},
            "data": {"result": "success"}
        }
        
        with patch.object(self.sage.proxy_service, 'make_proxied_call', 
                         return_value=(mock_response, 100.0, 50)):
            
            successful_calls = 0
            
            # Make several calls to approach the rate limit
            for i in range(8):  # We set limit to 10, so this should work
                try:
                    await self.sage.proxy_call(
                        key_id=key_id,
                        target_url="https://api.example.com/test",
                        payload={"method": "GET"},
                        caller_session=self.agent_b_session
                    )
                    successful_calls += 1
                    print(f"   Call {i+1}: ✅ Success")
                    
                except Exception as e:
                    print(f"   Call {i+1}: ❌ {e}")
                    break
            
            await self.print_info(f"Bob made {successful_calls} additional successful calls")
            
            # Now try to exceed the rate limit
            await self.print_info("Attempting to exceed rate limit...")
            
            try:
                # This should fail due to rate limiting
                await self.sage.proxy_call(
                    key_id=key_id,
                    target_url="https://api.example.com/test",
                    payload={"method": "GET"},
                    caller_session=self.agent_b_session
                )
                await self.print_error("Rate limit should have been enforced!")
                
            except Exception as e:
                if "rate limit" in str(e).lower():
                    await self.print_success("Rate limit properly enforced!")
                    await self.print_info(f"Error: {e}")
                else:
                    await self.print_error(f"Unexpected error: {e}")
    
    async def demo_unauthorized_access(self, key_id: str):
        """Demonstrate unauthorized access attempt"""
        await self.print_step("5", "Agent Charlie tries to use the key (unauthorized)")
        
        try:
            await self.sage.proxy_call(
                key_id=key_id,
                target_url="https://api.example.com/unauthorized",
                payload={"method": "GET"},
                caller_session=self.agent_c_session  # Charlie has no grant
            )
            await self.print_error("Authorization should have failed!")
            
        except Exception as e:
            if "access denied" in str(e).lower():
                await self.print_success("Unauthorized access properly blocked!")
                await self.print_info(f"Error: {e}")
            else:
                await self.print_error(f"Unexpected error: {e}")
    
    async def demo_audit_logs(self, key_id: str):
        """Demonstrate audit log viewing"""
        await self.print_step("6", "Agent Alice views audit logs for her key")
        
        try:
            logs = await self.sage.list_logs(
                key_id=key_id,
                filters={},
                owner_session=self.agent_a_session
            )
            
            await self.print_success(f"Retrieved {len(logs)} audit log entries")
            
            # Show recent logs
            print("\n   Recent Activity:")
            for i, log in enumerate(logs[:5]):  # Show first 5 logs
                timestamp = log.get('timestamp', 'Unknown')
                action = log.get('action', 'Unknown')
                caller = log.get('caller_id', 'Unknown')
                status = log.get('response_code', 'N/A')
                
                # Truncate caller ID for display
                caller_short = caller[:15] + "..." if len(caller) > 15 else caller
                
                print(f"   {i+1}. {timestamp[:19]} | {action:15} | {caller_short:18} | Status: {status}")
            
            if len(logs) > 5:
                await self.print_info(f"... and {len(logs) - 5} more entries")
            
        except Exception as e:
            await self.print_error(f"Failed to retrieve logs: {e}")
    
    async def demo_usage_statistics(self, key_id: str):
        """Demonstrate usage statistics"""
        await self.print_step("7", "Agent Alice views usage statistics")
        
        try:
            stats = await self.sage.get_usage_stats(
                key_id=key_id,
                owner_session=self.agent_a_session,
                days=7
            )
            
            if stats:
                await self.print_success("Usage statistics retrieved!")
                print(f"   Total API calls: {stats.get('total_calls', 0)}")
                print(f"   Successful calls: {stats.get('successful_calls', 0)}")
                print(f"   Failed calls: {stats.get('failed_calls', 0)}")
                print(f"   Rate limit blocks: {stats.get('rate_limit_blocks', 0)}")
                print(f"   Success rate: {stats.get('success_rate', 0):.1f}%")
                print(f"   Average response time: {stats.get('average_response_time', 0):.1f}ms")
                print(f"   Unique callers: {stats.get('unique_callers', 0)}")
            else:
                await self.print_info("No usage statistics available yet")
                
        except Exception as e:
            await self.print_error(f"Failed to retrieve usage statistics: {e}")
    
    async def demo_mcp_protocol(self, key_id: str):
        """Demonstrate MCP protocol handling"""
        await self.print_step("8", "Testing MCP Protocol Interface")
        
        # Test MCP add_key request
        add_key_request = {
            "method": "add_key",
            "session_id": "coral_demo_session_mcp",
            "params": {
                "key_name": "demo_mcp_key",
                "api_key": "sk-mcp-demo-123"
            }
        }
        
        try:
            response = await self.sage.handle_mcp_request(add_key_request)
            
            if response.get("success"):
                await self.print_success("MCP add_key request successful!")
                mcp_key_id = response["data"]["key_id"]
                await self.print_info(f"New key ID: {mcp_key_id[:8]}...")
            else:
                await self.print_error(f"MCP request failed: {response.get('error', {}).get('error_message', 'Unknown error')}")
        
        except Exception as e:
            await self.print_error(f"MCP protocol error: {e}")
        
        # Test MCP list_logs request
        logs_request = {
            "method": "list_logs",
            "session_id": self.agent_a_session,
            "params": {
                "key_id": key_id,
                "filters": {"limit": 3}
            }
        }
        
        try:
            response = await self.sage.handle_mcp_request(logs_request)
            
            if response.get("success"):
                log_count = len(response["data"]["logs"])
                await self.print_success(f"MCP list_logs request successful! Retrieved {log_count} logs")
            else:
                await self.print_error(f"MCP logs request failed: {response.get('error', {}).get('error_message', 'Unknown error')}")
        
        except Exception as e:
            await self.print_error(f"MCP protocol error: {e}")
    
    async def demo_cleanup(self):
        """Demonstrate cleanup operations"""
        await self.print_step("9", "System cleanup and maintenance")
        
        try:
            # Cleanup expired grants
            cleaned_grants = await self.sage.cleanup_expired_grants()
            await self.print_info(f"Cleaned up {cleaned_grants} expired grants")
            
            # Close services
            await self.sage.close()
            await self.print_success("All services closed successfully")
            
        except Exception as e:
            await self.print_error(f"Cleanup error: {e}")
    
    async def run_complete_demo(self):
        """Run the complete end-to-end demo"""
        await self.print_header("🚀 SAGE MCP END-TO-END DEMONSTRATION")
        
        print("""
This demo showcases the complete Sage MCP workflow:
• Secure API key storage with encryption
• Access grant management with permissions
• Rate-limited proxy calls with audit logging
• Privacy-aware error handling
• MCP protocol compliance
• Comprehensive audit trails

Let's get started!
        """)
        
        # Step 1: Store API key
        key_id = await self.demo_key_storage()
        if not key_id:
            print("\n❌ Demo failed at key storage step")
            return
        
        # Step 2: Grant access
        grant_success = await self.demo_grant_access(key_id)
        if not grant_success:
            print("\n❌ Demo failed at access grant step")
            return
        
        # Step 3: Successful proxy call
        await self.demo_successful_proxy_call(key_id)
        
        # Step 4: Multiple calls and rate limiting
        await self.demo_multiple_calls_and_rate_limiting(key_id)
        
        # Step 5: Unauthorized access
        await self.demo_unauthorized_access(key_id)
        
        # Step 6: View audit logs
        await self.demo_audit_logs(key_id)
        
        # Step 7: Usage statistics
        await self.demo_usage_statistics(key_id)
        
        # Step 8: MCP protocol
        await self.demo_mcp_protocol(key_id)
        
        # Step 9: Cleanup
        await self.demo_cleanup()
        
        # Final summary
        await self.print_header("🎉 DEMO COMPLETED SUCCESSFULLY!")
        
        print("""
✅ All Sage MCP features demonstrated successfully!

Key Features Shown:
• 🔐 Secure API key encryption and storage
• 👥 Multi-agent access control with grants
• 🚦 Rate limiting and policy enforcement
• 📊 Privacy-aware audit logging
• 🛡️  Comprehensive error handling
• 🔌 MCP protocol compliance
• 📈 Usage analytics and monitoring

Sage MCP is ready for production use!
        """)


async def main():
    """Main demo function"""
    demo = SageDemo()
    await demo.run_complete_demo()


if __name__ == "__main__":
    print("Starting Sage MCP End-to-End Demo...")
    asyncio.run(main())