"""
适配器层
处理不同接口协议的转换和数据格式化
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, AsyncGenerator
from ..models import ScanResult


class BaseAdapter(ABC):
    """适配器基类"""
    
    @abstractmethod
    async def handle_request(self, request_data: Dict[str, Any]) -> Any:
        """处理请求"""
        pass
    
    @abstractmethod
    def format_response(self, result: ScanResult) -> Any:
        """格式化响应"""
        pass
    
    @abstractmethod
    def format_error(self, error: Exception) -> Any:
        """格式化错误"""
        pass


class StreamingAdapter(BaseAdapter):
    """流式适配器基类"""
    
    @abstractmethod
    async def handle_streaming_request(self, request_data: Dict[str, Any]) -> AsyncGenerator[Any, None]:
        """处理流式请求"""
        pass
    
    @abstractmethod
    def format_progress(self, progress: Any) -> Any:
        """格式化进度信息"""
        pass


from .cli_adapter import CLIAdapter

# MCP adapters are imported on demand to avoid dependency issues
__all__ = [
    "BaseAdapter",
    "StreamingAdapter", 
    "CLIAdapter",
]

def get_mcp_local_adapter():
    """延迟导入MCP本地适配器"""
    try:
        from .mcp_local_adapter import MCPLocalAdapter
        return MCPLocalAdapter
    except ImportError as e:
        raise ImportError("MCP库未安装，请安装: pip install mcp") from e

def get_mcp_remote_adapter():
    """延迟导入MCP远程适配器"""
    try:
        from .mcp_remote_adapter import MCPRemoteAdapter
        return MCPRemoteAdapter
    except ImportError as e:
        raise ImportError("MCP库未安装，请安装: pip install mcp") from e 