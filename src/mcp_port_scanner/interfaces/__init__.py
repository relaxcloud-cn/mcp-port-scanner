"""
多种接口实现
提供CLI、MCP本地、MCP远程等多种调用方式
"""

# CLI接口
from .cli_interface import CLIInterface, main as cli_main

# Python SDK（已存在）
try:
    from .python_sdk import PortScannerSDK, quick_scan, scan_network_quick
    _has_python_sdk = True
except ImportError:
    _has_python_sdk = False

__all__ = [
    # CLI接口
    "CLIInterface",
    "cli_main",
]

if _has_python_sdk:
    __all__.extend([
        "PortScannerSDK",
        "quick_scan", 
        "scan_network_quick",
    ])

def get_mcp_local_server():
    """延迟导入MCP本地服务器"""
    try:
        from .mcp_local_server import MCPLocalServer
        return MCPLocalServer
    except ImportError as e:
        raise ImportError("MCP库未安装，请安装: pip install mcp") from e 