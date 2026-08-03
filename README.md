# Chat_Proxy - Token-Efficient MCP Chatbot

A highly token-efficient customer service chatbot utilizing the Model Context Protocol (MCP) and a "Better Proxy" architecture.

## Why This Architecture?
Traditional LLM integrations inject entire product catalogs into the system prompt, which wastes thousands of tokens per turn and causes context bloat. 

Our **Better Proxy** architecture prevents this:
1. **Concise Prompting:** The system prompt is minimal.
2. **On-Demand Data (MCP):** Using the Model Context Protocol, the LLM only fetches product data *exactly when a user asks for it*.
3. **Hard Token Limits:** The proxy handles the LLM negotiation and enforces strict token ceilings, saving costs.

## Architecture Structure
- `proxy_server.py`: FastAPI server that handles UI routing and intercepts LLM API calls.
- `mcp_products.py`: A dedicated MCP server exposing tools to search the product database dynamically.
- `public/index.html`: A lightweight, clean web demo.
