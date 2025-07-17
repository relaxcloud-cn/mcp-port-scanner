"""
MCP端口扫描器模块入口点
"""

import asyncio
from .interfaces.mcp_local_server import main

if __name__ == "__main__":
    asyncio.run(main()) 