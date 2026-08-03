import os
import json
from dotenv import load_dotenv

load_dotenv()
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from openai import AsyncOpenAI
from mcp.client.sse import sse_client
from mcp.client.session import ClientSession

app = FastAPI(title="Chat_Proxy Proxy")

# Serve the frontend UI
app.mount("/public", StaticFiles(directory="public"), name="public")

client = AsyncOpenAI(
    api_key=os.getenv("PROXY_API_KEY", "your_api_key_here"),
    base_url=os.getenv("PROXY_BASE_URL", None)
)

class ChatRequest(BaseModel):
    message: str

# Token-optimized system prompt
SYSTEM_PROMPT = """You are a helpful and intelligent AI assistant. 
Answer the user's questions clearly and accurately. 
You can chat about any topic."""

async def call_mcp_tool(tool_name: str, arguments: dict):
    """Connects to the MCP server via SSE to execute tools on-demand."""
    try:
        # Connect to the FastMCP SSE endpoint
        async with sse_client("http://127.0.0.1:8001/sse") as streams:
            async with ClientSession(streams[0], streams[1]) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments)
                # Extract the text content from the MCP result
                return result.content[0].text if result.content else "No data returned."
    except Exception as e:
        return f"Error contacting MCP server: {str(e)}"

@app.post("/chat")
async def chat(request: ChatRequest):
    try:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": request.message}
        ]
        
        # Expose the tool schema to the LLM so it knows it can search the catalog
        tools = [{
            "type": "function",
            "function": {
                "name": "search_products",
                "description": "Search the product catalog by name or description.",
                "parameters": {
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                    "required": ["query"]
                }
            }
        }]
        
        # First LLM call
        response = await client.chat.completions.create(
            model=os.getenv("PROXY_MODEL_NAME", "gpt-4o-mini"),
            messages=messages,
            tools=tools,
            max_tokens=150
        )
        
        msg = response.choices[0].message
        
        # If the LLM decides it needs product data from the MCP server
        if msg.tool_calls:
            messages.append(msg) # Append the assistant's tool call request
            
            for tool_call in msg.tool_calls:
                if tool_call.function.name == "search_products":
                    args = json.loads(tool_call.function.arguments)
                    
                    # Fetch data via MCP (Saves tokens by only loading what's needed)
                    mcp_result = await call_mcp_tool("search_products", args)
                    
                    # Append tool result to the conversation
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": mcp_result
                    })
            
            # Second LLM call with the context injected from the MCP tool
            final_response = await client.chat.completions.create(
                model=os.getenv("PROXY_MODEL_NAME", "gpt-4o-mini"),
                messages=messages,
                max_tokens=150
            )
            return {"response": final_response.choices[0].message.content}
        
        return {"response": msg.content}
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"response": f"Server Error: {str(e)}"}
