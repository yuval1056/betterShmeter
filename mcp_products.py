from fastmcp import FastMCP

# Initialize FastMCP Server for Server-Sent Events (SSE) transport
mcp = FastMCP("Chat_Proxy MCP")

# Mock Product Database
CATALOG = [
    {"id": "p1", "name": "Chat_Proxy Pro Laptop", "price": 1299, "stock": 45, "description": "High-performance laptop with 32GB RAM."},
    {"id": "p2", "name": "Chat_Proxy Wireless Mouse", "price": 49, "stock": 120, "description": "Ergonomic wireless mouse with 6 buttons."},
    {"id": "p3", "name": "Chat_Proxy Mechanical Keyboard", "price": 149, "stock": 0, "description": "Tactile mechanical keyboard, out of stock."}
]

@mcp.tool()
def search_products(query: str) -> str:
    """Search for products in the Chat_Proxy catalog by name or description."""
    query = query.lower()
    results = [p for p in CATALOG if query in p["name"].lower() or query in p["description"].lower()]
    
    if not results:
        return "No products found."
    
    # Return a concise string to save LLM tokens instead of a heavy JSON object
    return "\n".join([f"{p['name']} - ${p['price']} (Stock: {p['stock']})" for p in results])

if __name__ == "__main__":
    print("Starting Chat_Proxy MCP Server on port 8001...")
    mcp.run(transport="sse", port=8001)
