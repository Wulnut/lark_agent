from src.mcp_server import mcp
import logging
import sys

# Configure logging to write to a file in log directory
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    filename="log/agent.log",
    filemode="a",
    encoding="utf-8",
)

if __name__ == "__main__":
    mcp.run()
