from mcp.server.fastmcp import FastMCP
from src.tools.claims_tools import analyze_claim_image_async
import asyncio
import json

# Initialize FastMCP server
mcp = FastMCP("DirIA Claims Agent")

@mcp.tool()
async def analyze_claim_image(service_number: str, image_bytes: bytes, filename: str, mime_type: str = "image/jpeg") -> str:
    """
    Analyzes a claim image using the DirIA Vision Service.
    Returns the analysis result as a JSON string.
    """
    try:
        result = await analyze_claim_image_async(service_number, image_bytes, filename, mime_type)
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})

if __name__ == "__main__":
    mcp.run()
