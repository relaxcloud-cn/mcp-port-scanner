"""
MCP本地服务器（stdio）
基于适配器架构的MCP协议实现
"""

import asyncio
from typing import Dict, Any, List, Sequence
from mcp.server import Server
from mcp.types import Tool, TextContent
from mcp.server.stdio import stdio_server

from ..adapters.mcp_local_adapter import MCPLocalAdapter
from ..service import ScanService


class MCPLocalServer:
    """MCP本地服务器"""
    
    def __init__(self):
        self.server = Server("port-scanner")
        self.service = ScanService()
        self.adapter = MCPLocalAdapter(self.service)
        self._setup_tools()
    
    def _setup_tools(self) -> None:
        """设置MCP工具"""
        
        @self.server.list_tools()
        async def list_tools() -> List[Tool]:
            """列出可用的工具"""
            return [
                Tool(
                    name="scan_target",
                    description="对单个IP地址进行智能分层端口扫描",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "ip": {
                                "type": "string",
                                "description": "目标IP地址"
                            },
                            "ports": {
                                "type": "array",
                                "items": {"type": "integer"},
                                "description": "指定端口列表（可选，默认扫描常规端口）"
                            },
                            "scan_layers": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "扫描层级（可选）",
                                "enum": ["port_scan", "http_detection", "web_probe"],
                                "default": ["port_scan", "http_detection", "web_probe"]
                            },
                            "config": {
                                "type": "object",
                                "description": "扫描配置（可选）",
                                "properties": {
                                    "rustscan_timeout": {"type": "integer", "default": 3000},
                                    "banner_timeout": {"type": "number", "default": 5.0},
                                    "http_timeout": {"type": "number", "default": 10.0},
                                    "admin_scan_enabled": {"type": "boolean", "default": True},
                                    "admin_scan_threads": {"type": "integer", "default": 10}
                                }
                            }
                        },
                        "required": ["ip"]
                    }
                ),
                Tool(
                    name="batch_scan",
                    description="批量扫描多个IP地址",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "targets": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "ip": {"type": "string"},
                                        "ports": {
                                            "type": "array",
                                            "items": {"type": "integer"}
                                        }
                                    },
                                    "required": ["ip"]
                                },
                                "description": "扫描目标列表"
                            },
                            "scan_layers": {
                                "type": "array",
                                "items": {"type": "string"},
                                "enum": ["port_scan", "http_detection", "web_probe"],
                                "default": ["port_scan", "http_detection", "web_probe"]
                            },
                            "max_concurrent": {
                                "type": "integer",
                                "default": 5,
                                "description": "最大并发扫描数"
                            }
                        },
                        "required": ["targets"]
                    }
                ),
                Tool(
                    name="get_scan_status",
                    description="获取扫描状态",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "scan_id": {
                                "type": "string",
                                "description": "扫描ID"
                            }
                        },
                        "required": ["scan_id"]
                    }
                ),
                Tool(
                    name="get_scan_result",
                    description="获取扫描结果",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "scan_id": {
                                "type": "string",
                                "description": "扫描ID"
                            }
                        },
                        "required": ["scan_id"]
                    }
                ),
                Tool(
                    name="list_active_scans",
                    description="列出所有活跃的扫描任务",
                    inputSchema={
                        "type": "object",
                        "properties": {}
                    }
                ),
                Tool(
                    name="quick_scan",
                    description="快速端口扫描（仅端口扫描层）",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "ip": {
                                "type": "string",
                                "description": "目标IP地址"
                            },
                            "ports": {
                                "type": "array",
                                "items": {"type": "integer"},
                                "description": "指定端口列表（可选）"
                            }
                        },
                        "required": ["ip"]
                    }
                ),
                Tool(
                    name="scan_network",
                    description="扫描整个网络段",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "network": {
                                "type": "string",
                                "description": "网络段（如 192.168.1.0/24）"
                            },
                            "max_concurrent": {
                                "type": "integer",
                                "default": 10,
                                "description": "最大并发扫描数"
                            },
                            "scan_layers": {
                                "type": "array",
                                "items": {"type": "string"},
                                "enum": ["port_scan", "http_detection", "web_probe"],
                                "default": ["port_scan", "http_detection"]
                            }
                        },
                        "required": ["network"]
                    }
                )
            ]
        
        @self.server.call_tool()
        async def call_tool(name: str, arguments: Dict[str, Any]) -> Sequence[TextContent]:
            """调用工具"""
            try:
                if name == "scan_target":
                    return await self._handle_scan_target(arguments)
                elif name == "batch_scan":
                    return await self._handle_batch_scan(arguments)
                elif name == "get_scan_status":
                    return await self._handle_get_scan_status(arguments)
                elif name == "get_scan_result":
                    return await self._handle_get_scan_result(arguments)
                elif name == "list_active_scans":
                    return await self._handle_list_active_scans(arguments)
                elif name == "quick_scan":
                    return await self._handle_quick_scan(arguments)
                elif name == "scan_network":
                    return await self._handle_scan_network(arguments)
                else:
                    return [TextContent(type="text", text=f"未知工具: {name}")]
            except Exception as e:
                return self.adapter.format_error(e)
    
    async def _handle_scan_target(self, arguments: Dict[str, Any]) -> Sequence[TextContent]:
        """处理单个目标扫描"""
        request_data = {
            "tool_name": "scan_target",
            "arguments": arguments
        }
        
        result = await self.adapter.handle_request(request_data)
        return self.adapter.format_response(result)
    
    async def _handle_batch_scan(self, arguments: Dict[str, Any]) -> Sequence[TextContent]:
        """处理批量扫描"""
        request_data = {
            "tool_name": "batch_scan",
            "arguments": arguments
        }
        
        result = await self.adapter.handle_request(request_data)
        return self.adapter.format_response(result)
    
    async def _handle_get_scan_status(self, arguments: Dict[str, Any]) -> Sequence[TextContent]:
        """获取扫描状态"""
        request_data = {
            "tool_name": "get_scan_status",
            "arguments": arguments
        }
        
        result = await self.adapter.handle_request(request_data)
        return self.adapter.format_response(result)
    
    async def _handle_get_scan_result(self, arguments: Dict[str, Any]) -> Sequence[TextContent]:
        """获取扫描结果"""
        request_data = {
            "tool_name": "get_scan_result",
            "arguments": arguments
        }
        
        result = await self.adapter.handle_request(request_data)
        return self.adapter.format_response(result)
    
    async def _handle_list_active_scans(self, arguments: Dict[str, Any]) -> Sequence[TextContent]:
        """列出活跃扫描"""
        return self.adapter.get_active_scans_summary()
    
    async def _handle_quick_scan(self, arguments: Dict[str, Any]) -> Sequence[TextContent]:
        """快速扫描（仅端口扫描）"""
        # 修改参数以仅执行端口扫描
        modified_args = arguments.copy()
        modified_args["scan_layers"] = ["port_scan"]
        
        request_data = {
            "tool_name": "scan_target",
            "arguments": modified_args
        }
        
        result = await self.adapter.handle_request(request_data)
        return self.adapter.format_response(result)
    
    async def _handle_scan_network(self, arguments: Dict[str, Any]) -> Sequence[TextContent]:
        """扫描网络段"""
        try:
            import ipaddress
            
            network = arguments["network"]
            max_concurrent = arguments.get("max_concurrent", 10)
            scan_layers = arguments.get("scan_layers", ["port_scan", "http_detection"])
            
            # 解析网络段
            net = ipaddress.IPv4Network(network, strict=False)
            hosts = list(net.hosts())
            
            # 限制扫描数量（避免过大的网络段）
            if len(hosts) > 512:
                return [TextContent(
                    type="text", 
                    text=f"❌ 网络段过大 ({len(hosts)} 个主机)，最大支持 512 个主机"
                )]
            
            # 转换为批量扫描格式
            targets = [{"ip": str(ip)} for ip in hosts]
            
            batch_args = {
                "targets": targets,
                "scan_layers": scan_layers,
                "max_concurrent": max_concurrent
            }
            
            request_data = {
                "tool_name": "batch_scan",
                "arguments": batch_args
            }
            
            # 添加网络扫描的特殊提示
            result = await self.adapter.handle_request(request_data)
            response = self.adapter.format_response(result)
            
            # 在结果前添加网络信息
            network_info = TextContent(
                type="text",
                text=f"🌐 网络段扫描: {network} ({len(hosts)} 个主机)\n"
            )
            
            return [network_info] + list(response)
            
        except ValueError as e:
            return [TextContent(type="text", text=f"❌ 无效的网络段格式: {e}")]
        except Exception as e:
            return self.adapter.format_error(e)
    
    async def run(self) -> None:
        """运行MCP服务器"""
        async with stdio_server() as streams:
            await self.server.run(
                streams[0], streams[1],
                self.server.create_initialization_options()
            )


# 服务器入口点
async def main():
    """主函数"""
    server = MCPLocalServer()
    await server.run()


if __name__ == "__main__":
    asyncio.run(main()) 