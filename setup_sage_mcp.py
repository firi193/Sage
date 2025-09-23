#!/usr/bin/env python3
"""
Setup script for Sage MCP Server

This script helps you set up and test the Sage MCP server for use with Coral agents.
"""

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path


def print_header(title: str):
    """Print a formatted header"""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def print_step(step: str, description: str):
    """Print a formatted step"""
    print(f"\n🔹 Step {step}: {description}")
    print("-" * 50)


def print_success(message: str):
    """Print a success message"""
    print(f"✅ {message}")


def print_error(message: str):
    """Print an error message"""
    print(f"❌ {message}")


def print_info(message: str):
    """Print an info message"""
    print(f"ℹ️  {message}")


def check_python_version():
    """Check if Python version is compatible"""
    if sys.version_info < (3, 8):
        print_error("Python 3.8 or higher is required")
        return False
    print_success(f"Python {sys.version_info.major}.{sys.version_info.minor} detected")
    return True


def install_dependencies():
    """Install required dependencies"""
    print_step("1", "Installing MCP dependencies")
    
    try:
        # Install MCP package
        subprocess.run([
            sys.executable, "-m", "pip", "install", 
            "mcp", "pydantic>=2.0.0", "anyio>=4.0.0"
        ], check=True, capture_output=True)
        
        print_success("MCP dependencies installed successfully")
        return True
        
    except subprocess.CalledProcessError as e:
        print_error(f"Failed to install dependencies: {e}")
        print("You may need to install manually:")
        print("  pip install mcp pydantic anyio")
        return False


def test_sage_import():
    """Test if Sage modules can be imported"""
    print_step("2", "Testing Sage module imports")
    
    try:
        from sage.sage_mcp import SageMCP
        print_success("Sage modules imported successfully")
        return True
    except ImportError as e:
        print_error(f"Failed to import Sage modules: {e}")
        print("Make sure you're running from the project root directory")
        return False


def create_mcp_config():
    """Create MCP configuration for Coral"""
    print_step("3", "Creating MCP configuration")
    
    config_path = Path("sage_mcp_config.json")
    
    if config_path.exists():
        print_info("MCP configuration already exists")
        return True
    
    config = {
        "mcpServers": {
            "sage-api-key-manager": {
                "command": "python",
                "args": [str(Path("sage_mcp_server.py").absolute())],
                "env": {
                    "PYTHONPATH": str(Path(".").absolute()),
                    "SAGE_LOG_LEVEL": "INFO"
                },
                "description": "Secure API key management and proxying service for Coral agents"
            }
        }
    }
    
    try:
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
        
        print_success(f"MCP configuration created: {config_path}")
        return True
        
    except Exception as e:
        print_error(f"Failed to create MCP configuration: {e}")
        return False


def test_mcp_server():
    """Test if the MCP server can start"""
    print_step("4", "Testing MCP server startup")
    
    try:
        # Import and test server creation
        import sage_mcp_server
        print_success("MCP server module loaded successfully")
        
        print_info("Server appears to be configured correctly")
        print_info("To start the server, run: python sage_mcp_server.py")
        return True
        
    except Exception as e:
        print_error(f"MCP server test failed: {e}")
        return False


def show_coral_integration_instructions():
    """Show instructions for integrating with Coral"""
    print_step("5", "Coral Integration Instructions")
    
    print("""
🔌 To connect Sage to Coral agents:

1. Copy the MCP configuration to your Coral MCP config:
   
   For workspace-level config (.kiro/settings/mcp.json):
   {
     "mcpServers": {
       "sage-api-key-manager": {
         "command": "python",
         "args": ["/full/path/to/sage_mcp_server.py"],
         "env": {
           "PYTHONPATH": "/full/path/to/sage/project"
         }
       }
     }
   }

2. Or use uvx to run it (recommended):
   {
     "mcpServers": {
       "sage-api-key-manager": {
         "command": "uvx",
         "args": ["--from", "/path/to/sage", "sage_mcp_server.py"]
       }
     }
   }

3. Available tools for Coral agents:
   • store_api_key - Store encrypted API keys
   • grant_key_access - Grant access to other agents  
   • proxy_api_call - Make API calls with shared keys
   • list_my_keys - List your stored keys
   • view_audit_logs - View usage audit logs
   • get_usage_statistics - Get usage analytics
   • revoke_api_key - Revoke keys and grants

4. Example usage in Coral agent:
   "Store my OpenAI API key as 'production_key'"
   "Grant access to agent_bob for 100 calls per day"
   "Make an API call to OpenAI using my production_key"
    """)


def main():
    """Main setup function"""
    print_header("🚀 SAGE MCP SERVER SETUP")
    
    print("""
This script will help you set up Sage as an MCP server for Coral agents.
Sage provides secure API key management and proxying with:
• Encrypted key storage
• Multi-agent access control
• Rate limiting and audit logging
• Privacy-aware error handling
    """)
    
    # Check Python version
    if not check_python_version():
        return 1
    
    # Install dependencies
    if not install_dependencies():
        print_info("You can continue setup and install dependencies manually later")
    
    # Test Sage imports
    if not test_sage_import():
        print_error("Cannot proceed without Sage modules")
        return 1
    
    # Create MCP config
    if not create_mcp_config():
        print_error("Failed to create MCP configuration")
        return 1
    
    # Test MCP server
    if not test_mcp_server():
        print_error("MCP server test failed")
        return 1
    
    # Show integration instructions
    show_coral_integration_instructions()
    
    print_header("✅ SETUP COMPLETED SUCCESSFULLY!")
    
    print("""
Next steps:
1. Add the MCP configuration to your Coral settings
2. Start using Sage tools in your Coral agents
3. Run 'python sage_mcp_server.py' to start the server manually (for testing)

For testing, you can also run:
• python demo_sage_end_to_end.py (automated demo)
• python interactive_sage_demo.py (interactive testing)
    """)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())