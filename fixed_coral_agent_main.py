import os
import json
import asyncio
import traceback
from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langchain.prompts import ChatPromptTemplate
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain.agents import create_tool_calling_agent, AgentExecutor

load_dotenv()

def get_tools_description(tools):
    return "\n".join(
        f"Tool: {tool.name}, Schema: {json.dumps(tool.args).replace('{', '{{').replace('}', '}}')}"
        for tool in tools
    )

async def create_agent(agent_tools):
    agent_tools_description = get_tools_description(agent_tools)
    
    prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            f"""You are the Sage API Key Management agent. You can:
            - Manage API keys and access permissions
            - Perform health checks
            - Proxy API calls with security policies
            - Retrieve usage statistics and logs
            - Handle grant lifecycle including cleanup of expired permissions

            Available tools: {agent_tools_description}
            
            When asked to perform any task, use the appropriate tools to complete it.
            Always provide clear feedback about what you've done.
            """
        ),
        ("placeholder", "{agent_scratchpad}")
    ])

    model = init_chat_model(
        model=os.getenv("MODEL_NAME", "gpt-4o-mini"),
        model_provider=os.getenv("MODEL_PROVIDER", "openai"),
        api_key=os.getenv("OPENAI_API_KEY"),
        temperature=float(os.getenv("MODEL_TEMPERATURE", "0.1")),
        max_tokens=int(os.getenv("MODEL_TOKEN", "8000")),
    )
    
    agent = create_tool_calling_agent(model, agent_tools, prompt)
    return AgentExecutor(agent=agent, tools=agent_tools, verbose=True)

async def main():
    print("Starting Sage MCP Agent...")
    
    # Connect only to your Sage MCP server
    client = MultiServerMCPClient(
        connections={
            "sage_mcp": {
                "transport": "sse",
                "url": "http://172.30.208.1:8001/sse",
                "description": "Sage API Key Management and Proxy Service"
            }
        }
    )

    print("Connected to Sage MCP Server")
    
    # Get tools from your Sage server
    agent_tools = await client.get_tools()  # Remove server_name parameter
    print(f"Loaded {len(agent_tools)} tools from Sage MCP server")
    
    # List available tools
    for tool in agent_tools:
        print(f"- {tool.name}: {tool.description}")
    
    # Create the agent
    agent_executor = await create_agent(agent_tools)
    
    print("\nSage Agent is ready! You can now interact with it.")
    print("Available commands:")
    print("- Add API key")
    print("- Grant access")
    print("- Proxy API calls")
    print("- Check health")
    print("- View logs")
    print("- Cleanup expired grants")
    
    # Interactive mode
    while True:
        try:
            user_input = input("\nWhat would you like me to do? (or 'quit' to exit): ")
            if user_input.lower() in ['quit', 'exit', 'q']:
                break
                
            print(f"\nProcessing: {user_input}")
            result = await agent_executor.ainvoke({"input": user_input})
            print(f"\nResult: {result.get('output', 'No output')}")
            
        except KeyboardInterrupt:
            print("\nExiting...")
            break
        except Exception as e:
            print(f"Error: {str(e)}")
            print(traceback.format_exc())
            await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(main())