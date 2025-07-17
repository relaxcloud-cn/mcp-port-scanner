"""
MCP本地服务器（stdio）
基于适配器架构的MCP协议实现
"""

import asyncio
import time
from typing import Dict, Any, List, Sequence
from mcp.server import Server
from mcp.types import Tool, TextContent
from mcp.server.stdio import stdio_server

from ..adapters.mcp_local_adapter import MCPLocalAdapter
from ..service import ScanService
from ..logger_config import logger


class MCPLocalServer:
    """MCP本地服务器"""
    
    def __init__(self):
        logger.info("MCPLocalServer: 开始初始化...")
        
        self.server = Server("port-scanner")
        logger.debug("MCPLocalServer: MCP Server 实例创建完成")
        
        self.service = ScanService()
        logger.debug("MCPLocalServer: ScanService 实例创建完成")
        
        self.adapter = MCPLocalAdapter(self.service)
        logger.debug("MCPLocalServer: MCPLocalAdapter 实例创建完成")
        
        logger.info("MCPLocalServer: 初始化完成，服务名称: port-scanner")
        self._setup_tools()
        logger.info("MCPLocalServer: 工具设置完成，服务器准备就绪")
    
    def _setup_tools(self) -> None:
        """设置MCP工具"""
        logger.debug("MCPLocalServer._setup_tools: 开始设置工具...")
        
        @self.server.list_tools()
        async def list_tools() -> List[Tool]:
            """列出可用的工具"""
            logger.debug("list_tools: 客户端请求工具列表")
            tools_count = 7  # 当前支持的工具数量
            logger.info(f"list_tools: 返回 {tools_count} 个可用工具")
            
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
            start_time = time.time()
            logger.info(f"call_tool: 收到工具调用请求 - 工具名: {name}")
            logger.debug(f"call_tool: 调用参数 - {arguments}")
            
            try:
                if name == "scan_target":
                    result = await self._handle_scan_target(arguments)
                elif name == "batch_scan":
                    result = await self._handle_batch_scan(arguments)
                elif name == "get_scan_status":
                    result = await self._handle_get_scan_status(arguments)
                elif name == "get_scan_result":
                    result = await self._handle_get_scan_result(arguments)
                elif name == "list_active_scans":
                    result = await self._handle_list_active_scans(arguments)
                elif name == "quick_scan":
                    result = await self._handle_quick_scan(arguments)
                elif name == "scan_network":
                    result = await self._handle_scan_network(arguments)
                else:
                    logger.warning(f"call_tool: 未知工具名称: {name}")
                    result = [TextContent(type="text", text=f"未知工具: {name}")]
                
                execution_time = time.time() - start_time
                logger.info(f"call_tool: 工具 {name} 执行完成，耗时: {execution_time:.3f}秒")
                return result
                
            except Exception as e:
                execution_time = time.time() - start_time
                logger.error(f"call_tool: 工具 {name} 执行失败，耗时: {execution_time:.3f}秒，错误: {str(e)}", exc_info=True)
                return self.adapter.format_error(e)
        
        logger.debug("MCPLocalServer._setup_tools: 工具设置完成")
    
    async def _handle_scan_target(self, arguments: Dict[str, Any]) -> Sequence[TextContent]:
        """处理单个目标扫描"""
        ip = arguments.get("ip")
        scan_layers = arguments.get("scan_layers", ["port_scan", "http_detection", "web_probe"])
        ports = arguments.get("ports")
        
        logger.info(f"_handle_scan_target: 开始单目标扫描 - IP: {ip}, 扫描层级: {scan_layers}")
        if ports:
            logger.debug(f"_handle_scan_target: 指定端口: {ports}")
        
        try:
            request_data = {
                "tool_name": "scan_target",
                "arguments": arguments
            }
            
            result = await self.adapter.handle_request(request_data)
            
            # 记录扫描结果统计
            if isinstance(result, dict) and "scan_id" in result:
                logger.info(f"_handle_scan_target: 扫描任务已启动 - 扫描ID: {result['scan_id']}")
            
            response = self.adapter.format_response(result)
            logger.debug(f"_handle_scan_target: 响应格式化完成，返回 {len(response)} 个内容块")
            return response
            
        except Exception as e:
            logger.error(f"_handle_scan_target: 处理失败 - IP: {ip}, 错误: {str(e)}", exc_info=True)
            raise
    
    async def _handle_batch_scan(self, arguments: Dict[str, Any]) -> Sequence[TextContent]:
        """处理批量扫描"""
        targets = arguments.get("targets", [])
        scan_layers = arguments.get("scan_layers", ["port_scan", "http_detection", "web_probe"])
        max_concurrent = arguments.get("max_concurrent", 5)
        
        logger.info(f"_handle_batch_scan: 开始批量扫描 - 目标数量: {len(targets)}, 并发数: {max_concurrent}, 扫描层级: {scan_layers}")
        logger.debug(f"_handle_batch_scan: 目标列表: {[t.get('ip') for t in targets]}")
        
        try:
            request_data = {
                "tool_name": "batch_scan",
                "arguments": arguments
            }
            
            result = await self.adapter.handle_request(request_data)
            
            # 记录批量扫描结果统计
            if isinstance(result, dict) and "scan_id" in result:
                logger.info(f"_handle_batch_scan: 批量扫描任务已启动 - 扫描ID: {result['scan_id']}")
            
            response = self.adapter.format_response(result)
            logger.debug(f"_handle_batch_scan: 响应格式化完成，返回 {len(response)} 个内容块")
            return response
            
        except Exception as e:
            logger.error(f"_handle_batch_scan: 处理失败 - 目标数量: {len(targets)}, 错误: {str(e)}", exc_info=True)
            raise
    
    async def _handle_get_scan_status(self, arguments: Dict[str, Any]) -> Sequence[TextContent]:
        """获取扫描状态"""
        scan_id = arguments.get("scan_id")
        logger.debug(f"_handle_get_scan_status: 查询扫描状态 - 扫描ID: {scan_id}")
        
        try:
            request_data = {
                "tool_name": "get_scan_status",
                "arguments": arguments
            }
            
            result = await self.adapter.handle_request(request_data)
            
            # 记录状态查询结果
            if isinstance(result, dict) and "status" in result:
                logger.debug(f"_handle_get_scan_status: 状态查询成功 - 扫描ID: {scan_id}, 状态: {result['status']}")
            
            response = self.adapter.format_response(result)
            return response
            
        except Exception as e:
            logger.error(f"_handle_get_scan_status: 查询失败 - 扫描ID: {scan_id}, 错误: {str(e)}", exc_info=True)
            raise
    
    async def _handle_get_scan_result(self, arguments: Dict[str, Any]) -> Sequence[TextContent]:
        """获取扫描结果"""
        scan_id = arguments.get("scan_id")
        logger.debug(f"_handle_get_scan_result: 获取扫描结果 - 扫描ID: {scan_id}")
        
        try:
            request_data = {
                "tool_name": "get_scan_result",
                "arguments": arguments
            }
            
            result = await self.adapter.handle_request(request_data)
            
            # 记录结果获取统计
            if isinstance(result, dict) and "result" in result:
                logger.debug(f"_handle_get_scan_result: 结果获取成功 - 扫描ID: {scan_id}")
                # 如果结果包含端口信息，记录统计
                if "open_ports" in result.get("result", {}):
                    open_ports_count = len(result["result"]["open_ports"])
                    logger.info(f"_handle_get_scan_result: 扫描完成 - 扫描ID: {scan_id}, 开放端口数: {open_ports_count}")
            
            response = self.adapter.format_response(result)
            return response
            
        except Exception as e:
            logger.error(f"_handle_get_scan_result: 获取失败 - 扫描ID: {scan_id}, 错误: {str(e)}", exc_info=True)
            raise
    
    async def _handle_list_active_scans(self, arguments: Dict[str, Any]) -> Sequence[TextContent]:
        """列出活跃扫描"""
        logger.debug("_handle_list_active_scans: 获取活跃扫描列表")
        
        try:
            response = self.adapter.get_active_scans_summary()
            
            # 记录活跃扫描统计
            active_count = len(self.adapter.service.active_scans) if hasattr(self.adapter.service, 'active_scans') else 0
            logger.info(f"_handle_list_active_scans: 当前活跃扫描数量: {active_count}")
            
            return response
            
        except Exception as e:
            logger.error(f"_handle_list_active_scans: 获取失败, 错误: {str(e)}", exc_info=True)
            raise
    
    async def _handle_quick_scan(self, arguments: Dict[str, Any]) -> Sequence[TextContent]:
        """快速扫描（仅端口扫描）"""
        ip = arguments.get("ip")
        ports = arguments.get("ports")
        
        logger.info(f"_handle_quick_scan: 开始快速扫描 - IP: {ip}")
        if ports:
            logger.debug(f"_handle_quick_scan: 指定端口: {ports}")
        
        try:
            # 修改参数以仅执行端口扫描
            modified_args = arguments.copy()
            modified_args["scan_layers"] = ["port_scan"]
            
            logger.debug("_handle_quick_scan: 设置扫描层级为仅端口扫描")
            
            request_data = {
                "tool_name": "scan_target",
                "arguments": modified_args
            }
            
            result = await self.adapter.handle_request(request_data)
            
            # 记录快速扫描结果
            if isinstance(result, dict) and "scan_id" in result:
                logger.info(f"_handle_quick_scan: 快速扫描任务已启动 - 扫描ID: {result['scan_id']}")
            
            response = self.adapter.format_response(result)
            return response
            
        except Exception as e:
            logger.error(f"_handle_quick_scan: 处理失败 - IP: {ip}, 错误: {str(e)}", exc_info=True)
            raise
    
    async def _handle_scan_network(self, arguments: Dict[str, Any]) -> Sequence[TextContent]:
        """扫描网络段"""
        network = arguments.get("network")
        max_concurrent = arguments.get("max_concurrent", 10)
        scan_layers = arguments.get("scan_layers", ["port_scan", "http_detection"])
        
        logger.info(f"_handle_scan_network: 开始网络段扫描 - 网络: {network}, 并发数: {max_concurrent}, 扫描层级: {scan_layers}")
        
        try:
            import ipaddress
            
            # 解析网络段
            logger.debug(f"_handle_scan_network: 解析网络段: {network}")
            net = ipaddress.IPv4Network(network, strict=False)
            hosts = list(net.hosts())
            
            logger.info(f"_handle_scan_network: 网络段解析成功 - 主机数量: {len(hosts)}")
            
            # 限制扫描数量（避免过大的网络段）
            if len(hosts) > 512:
                logger.warning(f"_handle_scan_network: 网络段过大 - 主机数量: {len(hosts)}, 超过限制 512")
                return [TextContent(
                    type="text", 
                    text=f"❌ 网络段过大 ({len(hosts)} 个主机)，最大支持 512 个主机"
                )]
            
            # 转换为批量扫描格式
            targets = [{"ip": str(ip)} for ip in hosts]
            logger.debug(f"_handle_scan_network: 生成目标列表完成 - 目标数量: {len(targets)}")
            
            batch_args = {
                "targets": targets,
                "scan_layers": scan_layers,
                "max_concurrent": max_concurrent
            }
            
            request_data = {
                "tool_name": "batch_scan",
                "arguments": batch_args
            }
            
            logger.debug("_handle_scan_network: 开始执行批量扫描")
            
            # 添加网络扫描的特殊提示
            result = await self.adapter.handle_request(request_data)
            
            # 记录网络扫描结果
            if isinstance(result, dict) and "scan_id" in result:
                logger.info(f"_handle_scan_network: 网络段扫描任务已启动 - 扫描ID: {result['scan_id']}, 网络: {network}")
            
            response = self.adapter.format_response(result)
            
            # 在结果前添加网络信息
            network_info = TextContent(
                type="text",
                text=f"🌐 网络段扫描: {network} ({len(hosts)} 个主机)\n"
            )
            
            final_response = [network_info] + list(response)
            logger.debug(f"_handle_scan_network: 响应格式化完成，返回 {len(final_response)} 个内容块")
            return final_response
            
        except ValueError as e:
            logger.error(f"_handle_scan_network: 网络段格式无效 - 网络: {network}, 错误: {str(e)}")
            return [TextContent(type="text", text=f"❌ 无效的网络段格式: {e}")]
        except Exception as e:
            logger.error(f"_handle_scan_network: 处理失败 - 网络: {network}, 错误: {str(e)}", exc_info=True)
            return self.adapter.format_error(e)
    
    async def run(self) -> None:
        """运行MCP服务器"""
        logger.info("MCPLocalServer.run: 启动MCP服务器...")
        
        try:
            async with stdio_server() as streams:
                logger.info("MCPLocalServer.run: stdio服务器连接建立成功")
                logger.debug("MCPLocalServer.run: 开始运行服务器主循环")
                
                await self.server.run(
                    streams[0], streams[1],
                    self.server.create_initialization_options()
                )
                
        except Exception as e:
            logger.error(f"MCPLocalServer.run: 服务器运行失败，错误: {str(e)}", exc_info=True)
            raise
        finally:
            logger.info("MCPLocalServer.run: MCP服务器已停止")


# 服务器入口点
async def main():
    """主函数"""
    logger.info("main: MCP端口扫描服务启动中...")
    
    try:
        server = MCPLocalServer()
        logger.info("main: MCPLocalServer 实例创建完成，开始运行...")
        await server.run()
        
    except KeyboardInterrupt:
        logger.info("main: 收到中断信号，正在停止服务...")
    except Exception as e:
        logger.error(f"main: 服务运行失败，错误: {str(e)}", exc_info=True)
        raise
    finally:
        logger.info("main: MCP端口扫描服务已退出")


if __name__ == "__main__":
    asyncio.run(main()) 