#!/usr/bin/env python3
"""
Interactive Sage MCP Demo

This script provides an interactive command-line interface to test Sage MCP functionality.
You can manually test different scenarios and see the system in action.
"""

import asyncio
import json
from datetime import datetime
from unittest.mock import patch

from sage.sage_mcp import SageMCP


class InteractiveSageDemo:
    """Interactive demo for Sage MCP"""
    
    def __init__(self):
        self.sage = SageMCP()
        self.stored_keys = {}  # Track keys for demo
        self.current_session = None
    
    def print_menu(self):
        """Print the main menu"""
        print("\n" + "="*60)
        print("           🔐 SAGE MCP INTERACTIVE DEMO")
        print("="*60)
        print("1. 🔑 Store API Key")
        print("2. 👥 Grant Access to Another Agent")
        print("3. 🌐 Make Proxy API Call")
        print("4. 📋 List My Keys")
        print("5. 📊 View Audit Logs")
        print("6. 📈 View Usage Statistics")
        print("7. 🚫 Revoke Key")
        print("8. 🧪 Test Rate Limiting")
        print("9. 🔌 Test MCP Protocol")
        print("0. 🚪 Exit")
        print("-"*60)
    
    def get_input(self, prompt: str, default: str = None) -> str:
        """Get user input with optional default"""
        if default:
            user_input = input(f"{prompt} [{default}]: ").strip()
            return user_input if user_input else default
        return input(f"{prompt}: ").strip()
    
    def get_session_id(self) -> str:
        """Get or set current session ID"""
        if not self.current_session:
            self.current_session = self.get_input(
                "Enter your Coral session ID", 
                "coral_demo_user_session_123"
            )
        return self.current_session
    
    async def store_api_key(self):
        """Interactive API key storage"""
        print("\n🔑 Store API Key")
        print("-" * 30)
        
        session_id = self.get_session_id()
        key_name = self.get_input("Enter key name", "my_openai_key")
        api_key = self.get_input("Enter API key", "sk-demo123456789abcdef")
        
        try:
            key_id = await self.sage.add_key(
                key_name=key_name,
                api_key=api_key,
                owner_session=session_id
            )
            
            self.stored_keys[key_name] = key_id
            print(f"✅ Key stored successfully!")
            print(f"   Key ID: {key_id}")
            print(f"   Name: {key_name}")
            
        except Exception as e:
            print(f"❌ Error storing key: {e}")
    
    async def grant_access(self):
        """Interactive access granting"""
        print("\n👥 Grant Access to Another Agent")
        print("-" * 35)
        
        if not self.stored_keys:
            print("❌ No keys stored yet. Please store a key first.")
            return
        
        # Show available keys
        print("Available keys:")
        for i, (name, key_id) in enumerate(self.stored_keys.items(), 1):
            print(f"   {i}. {name} ({key_id[:8]}...)")
        
        key_choice = self.get_input("Select key number", "1")
        try:
            key_name = list(self.stored_keys.keys())[int(key_choice) - 1]
            key_id = self.stored_keys[key_name]
        except (ValueError, IndexError):
            print("❌ Invalid key selection")
            return
        
        caller_id = self.get_input("Enter caller's Coral session ID", "coral_other_agent_456")
        max_calls = int(self.get_input("Max calls per day", "10"))
        expiry_hours = int(self.get_input("Grant expiry (hours)", "24"))
        
        permissions = {"max_calls_per_day": max_calls}
        
        try:
            success = await self.sage.grant_access(
                key_id=key_id,
                caller_id=caller_id,
                permissions=permissions,
                expiry=expiry_hours,
                owner_session=self.get_session_id()
            )
            
            if success:
                print(f"✅ Access granted successfully!")
                print(f"   Key: {key_name}")
                print(f"   Caller: {caller_id}")
                print(f"   Max calls/day: {max_calls}")
                print(f"   Expires in: {expiry_hours} hours")
            else:
                print("❌ Failed to grant access")
                
        except Exception as e:
            print(f"❌ Error granting access: {e}")
    
    async def make_proxy_call(self):
        """Interactive proxy call"""
        print("\n🌐 Make Proxy API Call")
        print("-" * 25)
        
        if not self.stored_keys:
            print("❌ No keys available. Please store a key first.")
            return
        
        # Show available keys
        print("Available keys:")
        for i, (name, key_id) in enumerate(self.stored_keys.items(), 1):
            print(f"   {i}. {name} ({key_id[:8]}...)")
        
        key_choice = self.get_input("Select key number", "1")
        try:
            key_name = list(self.stored_keys.keys())[int(key_choice) - 1]
            key_id = self.stored_keys[key_name]
        except (ValueError, IndexError):
            print("❌ Invalid key selection")
            return
        
        target_url = self.get_input("Enter target URL", "https://api.openai.com/v1/chat/completions")
        method = self.get_input("HTTP method", "POST").upper()
        
        # Mock response for demo
        mock_response = {
            "status_code": 200,
            "headers": {"content-type": "application/json"},
            "data": {
                "id": "chatcmpl-demo",
                "choices": [{
                    "message": {
                        "role": "assistant", 
                        "content": "Hello! This is a demo response."
                    }
                }]
            }
        }
        
        with patch.object(self.sage.proxy_service, 'make_proxied_call', 
                         return_value=(mock_response, 120.0, 150)):
            
            try:
                response = await self.sage.proxy_call(
                    key_id=key_id,
                    target_url=target_url,
                    payload={
                        "method": method,
                        "headers": {"Content-Type": "application/json"},
                        "body": {"model": "gpt-3.5-turbo", "messages": []}
                    },
                    caller_session=self.get_session_id()
                )
                
                print(f"✅ Proxy call successful!")
                print(f"   Status: {response['status_code']}")
                print(f"   Response time: {response['response_time_ms']:.1f}ms")
                
                if response.get('data'):
                    print(f"   Response preview: {str(response['data'])[:100]}...")
                
            except Exception as e:
                print(f"❌ Proxy call failed: {e}")
    
    async def list_keys(self):
        """List stored keys"""
        print("\n📋 My Stored Keys")
        print("-" * 20)
        
        try:
            keys = await self.sage.list_keys(self.get_session_id())
            
            if keys:
                print(f"Found {len(keys)} key(s):")
                for i, key in enumerate(keys, 1):
                    print(f"   {i}. {key['key_name']}")
                    print(f"      ID: {key['key_id']}")
                    print(f"      Created: {key['created_at'][:19]}")
                    print(f"      Active: {'Yes' if key['is_active'] else 'No'}")
                    print()
            else:
                print("No keys found.")
                
        except Exception as e:
            print(f"❌ Error listing keys: {e}")
    
    async def view_audit_logs(self):
        """View audit logs"""
        print("\n📊 View Audit Logs")
        print("-" * 20)
        
        if not self.stored_keys:
            print("❌ No keys available.")
            return
        
        # Show available keys
        print("Select key to view logs:")
        for i, (name, key_id) in enumerate(self.stored_keys.items(), 1):
            print(f"   {i}. {name}")
        
        key_choice = self.get_input("Select key number", "1")
        try:
            key_name = list(self.stored_keys.keys())[int(key_choice) - 1]
            key_id = self.stored_keys[key_name]
        except (ValueError, IndexError):
            print("❌ Invalid key selection")
            return
        
        limit = int(self.get_input("Number of logs to show", "10"))
        
        try:
            logs = await self.sage.list_logs(
                key_id=key_id,
                filters={"limit": limit},
                owner_session=self.get_session_id()
            )
            
            if logs:
                print(f"\nShowing {len(logs)} most recent log entries:")
                print("-" * 80)
                print(f"{'Time':<20} {'Action':<15} {'Caller':<20} {'Status':<8}")
                print("-" * 80)
                
                for log in logs:
                    timestamp = log.get('timestamp', '')[:19]
                    action = log.get('action', 'Unknown')
                    caller = log.get('caller_id', 'Unknown')[:18]
                    status = log.get('response_code', 'N/A')
                    
                    print(f"{timestamp:<20} {action:<15} {caller:<20} {status:<8}")
            else:
                print("No logs found for this key.")
                
        except Exception as e:
            print(f"❌ Error retrieving logs: {e}")
    
    async def view_usage_stats(self):
        """View usage statistics"""
        print("\n📈 View Usage Statistics")
        print("-" * 25)
        
        if not self.stored_keys:
            print("❌ No keys available.")
            return
        
        # Show available keys
        print("Select key for statistics:")
        for i, (name, key_id) in enumerate(self.stored_keys.items(), 1):
            print(f"   {i}. {name}")
        
        key_choice = self.get_input("Select key number", "1")
        try:
            key_name = list(self.stored_keys.keys())[int(key_choice) - 1]
            key_id = self.stored_keys[key_name]
        except (ValueError, IndexError):
            print("❌ Invalid key selection")
            return
        
        days = int(self.get_input("Days to include", "7"))
        
        try:
            stats = await self.sage.get_usage_stats(
                key_id=key_id,
                owner_session=self.get_session_id(),
                days=days
            )
            
            if stats:
                print(f"\nUsage Statistics for '{key_name}' (last {days} days):")
                print("-" * 50)
                print(f"Total calls: {stats.get('total_calls', 0)}")
                print(f"Successful calls: {stats.get('successful_calls', 0)}")
                print(f"Failed calls: {stats.get('failed_calls', 0)}")
                print(f"Rate limit blocks: {stats.get('rate_limit_blocks', 0)}")
                print(f"Success rate: {stats.get('success_rate', 0):.1f}%")
                print(f"Avg response time: {stats.get('average_response_time', 0):.1f}ms")
                print(f"Unique callers: {stats.get('unique_callers', 0)}")
            else:
                print("No usage statistics available.")
                
        except Exception as e:
            print(f"❌ Error retrieving statistics: {e}")
    
    async def test_mcp_protocol(self):
        """Test MCP protocol"""
        print("\n🔌 Test MCP Protocol")
        print("-" * 22)
        
        # Test add_key via MCP
        print("Testing MCP add_key request...")
        
        request = {
            "method": "add_key",
            "session_id": self.get_session_id(),
            "params": {
                "key_name": "mcp_test_key",
                "api_key": "sk-mcp-test-123"
            }
        }
        
        try:
            response = await self.sage.handle_mcp_request(request)
            
            if response.get("success"):
                print("✅ MCP add_key successful!")
                print(f"   Key ID: {response['data']['key_id']}")
            else:
                error = response.get('error', {})
                print(f"❌ MCP add_key failed: {error.get('error_message', 'Unknown error')}")
                
        except Exception as e:
            print(f"❌ MCP protocol error: {e}")
    
    async def run_interactive_demo(self):
        """Run the interactive demo"""
        print("🚀 Welcome to the Sage MCP Interactive Demo!")
        print("This tool lets you test all Sage MCP features interactively.")
        
        while True:
            self.print_menu()
            choice = input("Select an option (0-9): ").strip()
            
            try:
                if choice == "1":
                    await self.store_api_key()
                elif choice == "2":
                    await self.grant_access()
                elif choice == "3":
                    await self.make_proxy_call()
                elif choice == "4":
                    await self.list_keys()
                elif choice == "5":
                    await self.view_audit_logs()
                elif choice == "6":
                    await self.view_usage_stats()
                elif choice == "7":
                    print("🚫 Key revocation feature - coming soon!")
                elif choice == "8":
                    print("🧪 Rate limiting test - coming soon!")
                elif choice == "9":
                    await self.test_mcp_protocol()
                elif choice == "0":
                    print("\n👋 Closing Sage MCP demo...")
                    await self.sage.close()
                    print("✅ Demo closed successfully. Goodbye!")
                    break
                else:
                    print("❌ Invalid option. Please select 0-9.")
                    
            except KeyboardInterrupt:
                print("\n\n👋 Demo interrupted. Closing...")
                await self.sage.close()
                break
            except Exception as e:
                print(f"❌ Unexpected error: {e}")
            
            input("\nPress Enter to continue...")


async def main():
    """Main function"""
    demo = InteractiveSageDemo()
    await demo.run_interactive_demo()


if __name__ == "__main__":
    asyncio.run(main())