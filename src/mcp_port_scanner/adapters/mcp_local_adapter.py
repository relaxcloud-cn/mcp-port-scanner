"""
MCP本地适配器
处理基于stdio的MCP协议请求和响应
"""

import json
import time
from typing import Any, Dict, List, Optional, Sequence
from datetime import datetime

from . import BaseAdapter
from ..service import ScanService
from ..models import ScanResult, ScanConfig, ScanTarget, ScanStatus
from mcp.types import TextContent
from ..logger_config import logger


class MCPLocalAdapter(BaseAdapter):
    """MCP本地适配器（stdio）"""
    
    def __init__(self, service: Optional[ScanService] = None):
        logger.debug("MCPLocalAdapter: 开始初始化...")
        self.service = service or ScanService()
        logger.info("MCPLocalAdapter: 初始化完成，服务实例准备就绪")
    
    async def handle_request(self, request_data: Dict[str, Any]) -> ScanResult:
        """
        处理MCP工具调用请求
        
        Args:
            request_data: MCP请求数据
                - tool_name: 工具名称
                - arguments: 工具参数
                
        Returns:
            ScanResult: 扫描结果
        """
        start_time = time.time()
        tool_name = request_data.get("tool_name")
        arguments = request_data.get("arguments", {})
        
        logger.info(f"MCPLocalAdapter.handle_request: 处理请求 - 工具: {tool_name}")
        logger.debug(f"MCPLocalAdapter.handle_request: 请求参数 - {arguments}")
        
        try:
            if tool_name == "scan_target":
                result = await self._handle_scan_target(arguments)
            elif tool_name == "batch_scan":
                result = await self._handle_batch_scan(arguments)
            elif tool_name == "get_scan_status":
                result = await self._handle_get_scan_status(arguments)
            elif tool_name == "get_scan_result":
                result = await self._handle_get_scan_result(arguments)
            else:
                logger.error(f"MCPLocalAdapter.handle_request: 不支持的工具 - {tool_name}")
                raise ValueError(f"不支持的工具: {tool_name}")
            
            execution_time = time.time() - start_time
            logger.info(f"MCPLocalAdapter.handle_request: 请求处理完成 - 工具: {tool_name}, 耗时: {execution_time:.3f}秒")
            return result
            
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"MCPLocalAdapter.handle_request: 请求处理失败 - 工具: {tool_name}, 耗时: {execution_time:.3f}秒, 错误: {str(e)}", exc_info=True)
            raise
    
    async def _handle_scan_target(self, arguments: Dict[str, Any]) -> ScanResult:
        """处理单目标扫描"""
        ip = arguments["ip"]
        ports = arguments.get("ports")
        scan_layers = arguments.get("scan_layers", ["port_scan", "http_detection", "web_probe"])
        config_dict = arguments.get("config", {})
        
        logger.info(f"MCPLocalAdapter._handle_scan_target: 开始单目标扫描 - IP: {ip}, 扫描层级: {scan_layers}")
        if ports:
            logger.debug(f"MCPLocalAdapter._handle_scan_target: 指定端口: {ports} ({len(ports)} 个)")
        else:
            logger.debug("MCPLocalAdapter._handle_scan_target: 使用默认端口范围")
        
        try:
            # 更新配置
            if config_dict:
                logger.debug(f"MCPLocalAdapter._handle_scan_target: 更新扫描配置 - {config_dict}")
                current_config = self.service.get_config()
                config_data = current_config.dict()
                config_data.update(config_dict)
                new_config = ScanConfig(**config_data)
                self.service.update_config(new_config)
                logger.info("MCPLocalAdapter._handle_scan_target: 扫描配置已更新")
            
            # 执行扫描
            logger.debug(f"MCPLocalAdapter._handle_scan_target: 开始执行扫描 - IP: {ip}")
            result = await self.service.scan_async(ip, ports, scan_layers)
            
            # 记录扫描结果统计
            if result:
                logger.info(f"MCPLocalAdapter._handle_scan_target: 扫描完成 - 扫描ID: {result.scan_id}, IP: {ip}, 状态: {result.status.value}")
                logger.debug(f"MCPLocalAdapter._handle_scan_target: 扫描统计 - 开放端口: {len(result.open_ports)}, HTTP服务: {len(result.http_services)}, 管理目录: {len(result.admin_directories)}")
            else:
                logger.warning(f"MCPLocalAdapter._handle_scan_target: 扫描返回空结果 - IP: {ip}")
            
            return result
            
        except Exception as e:
            logger.error(f"MCPLocalAdapter._handle_scan_target: 单目标扫描失败 - IP: {ip}, 错误: {str(e)}", exc_info=True)
            raise
    
    async def _handle_batch_scan(self, arguments: Dict[str, Any]) -> List[ScanResult]:
        """处理批量扫描"""
        targets_data = arguments["targets"]
        scan_layers = arguments.get("scan_layers", ["port_scan", "http_detection", "web_probe"])
        max_concurrent = arguments.get("max_concurrent", 5)
        
        logger.info(f"MCPLocalAdapter._handle_batch_scan: 开始批量扫描 - 目标数量: {len(targets_data)}, 并发数: {max_concurrent}, 扫描层级: {scan_layers}")
        logger.debug(f"MCPLocalAdapter._handle_batch_scan: 目标IP列表 - {[t.get('ip') for t in targets_data]}")
        
        try:
            # 转换目标格式
            logger.debug("MCPLocalAdapter._handle_batch_scan: 转换目标格式...")
            targets = []
            for i, target_data in enumerate(targets_data):
                target = ScanTarget(
                    ip=target_data["ip"],
                    ports=target_data.get("ports")
                )
                targets.append(target)
                if target_data.get("ports"):
                    logger.debug(f"MCPLocalAdapter._handle_batch_scan: 目标 {i+1} - {target.ip}, 指定端口: {len(target.ports)} 个")
            
            logger.info(f"MCPLocalAdapter._handle_batch_scan: 目标格式转换完成 - {len(targets)} 个目标")
            
            # 执行批量扫描
            logger.debug("MCPLocalAdapter._handle_batch_scan: 开始执行批量扫描...")
            results = await self.service.batch_scan_async(targets, scan_layers, max_concurrent)
            
            # 记录批量扫描结果统计
            if results:
                active_hosts = len([r for r in results if r.open_ports])
                total_ports = sum(len(r.open_ports) for r in results)
                total_http = sum(len(r.http_services) for r in results)
                total_admin = sum(len([d for d in r.admin_directories if d.is_admin]) for r in results)
                
                logger.info(f"MCPLocalAdapter._handle_batch_scan: 批量扫描完成 - 总目标: {len(results)}, 活跃主机: {active_hosts}")
                logger.info(f"MCPLocalAdapter._handle_batch_scan: 扫描统计 - 开放端口: {total_ports}, HTTP服务: {total_http}, 管理界面: {total_admin}")
            else:
                logger.warning("MCPLocalAdapter._handle_batch_scan: 批量扫描返回空结果")
            
            return results
            
        except Exception as e:
            logger.error(f"MCPLocalAdapter._handle_batch_scan: 批量扫描失败 - 目标数量: {len(targets_data)}, 错误: {str(e)}", exc_info=True)
            raise
    
    async def _handle_get_scan_status(self, arguments: Dict[str, Any]) -> Optional[ScanResult]:
        """获取扫描状态"""
        scan_id = arguments["scan_id"]
        logger.debug(f"MCPLocalAdapter._handle_get_scan_status: 查询扫描状态 - 扫描ID: {scan_id}")
        
        try:
            result = self.service.get_scan_status(scan_id)
            
            if result:
                logger.debug(f"MCPLocalAdapter._handle_get_scan_status: 状态查询成功 - 扫描ID: {scan_id}, 状态: {result.status.value}")
                if result.target:
                    logger.debug(f"MCPLocalAdapter._handle_get_scan_status: 目标信息 - IP: {result.target.ip}")
            else:
                logger.warning(f"MCPLocalAdapter._handle_get_scan_status: 未找到扫描记录 - 扫描ID: {scan_id}")
            
            return result
            
        except Exception as e:
            logger.error(f"MCPLocalAdapter._handle_get_scan_status: 状态查询失败 - 扫描ID: {scan_id}, 错误: {str(e)}", exc_info=True)
            raise
    
    async def _handle_get_scan_result(self, arguments: Dict[str, Any]) -> Optional[ScanResult]:
        """获取扫描结果"""
        scan_id = arguments["scan_id"]
        logger.debug(f"MCPLocalAdapter._handle_get_scan_result: 获取扫描结果 - 扫描ID: {scan_id}")
        
        try:
            result = self.service.get_scan_result(scan_id)
            
            if result:
                logger.info(f"MCPLocalAdapter._handle_get_scan_result: 结果获取成功 - 扫描ID: {scan_id}, IP: {result.target.ip if result.target else 'N/A'}")
                logger.debug(f"MCPLocalAdapter._handle_get_scan_result: 结果统计 - 开放端口: {len(result.open_ports)}, HTTP服务: {len(result.http_services)}, 管理目录: {len(result.admin_directories)}")
            else:
                logger.warning(f"MCPLocalAdapter._handle_get_scan_result: 未找到扫描结果 - 扫描ID: {scan_id}")
            
            return result
            
        except Exception as e:
            logger.error(f"MCPLocalAdapter._handle_get_scan_result: 结果获取失败 - 扫描ID: {scan_id}, 错误: {str(e)}", exc_info=True)
            raise
    
    def format_response(self, result: Any) -> Sequence[TextContent]:
        """
        格式化MCP响应
        
        Args:
            result: 扫描结果或结果列表
            
        Returns:
            Sequence[TextContent]: MCP文本内容列表
        """
        start_time = time.time()
        logger.debug(f"MCPLocalAdapter.format_response: 开始格式化响应 - 结果类型: {type(result).__name__}")
        
        try:
            if isinstance(result, list):
                # 批量扫描结果
                logger.debug(f"MCPLocalAdapter.format_response: 格式化批量扫描结果 - {len(result)} 个结果")
                response = self._format_batch_response(result)
            elif isinstance(result, ScanResult):
                # 单个扫描结果
                logger.debug(f"MCPLocalAdapter.format_response: 格式化单个扫描结果 - 扫描ID: {result.scan_id}")
                response = self._format_single_response(result)
            elif result is None:
                logger.warning("MCPLocalAdapter.format_response: 结果为空，返回未找到消息")
                response = [TextContent(type="text", text="未找到请求的扫描结果")]
            else:
                logger.warning(f"MCPLocalAdapter.format_response: 未知结果类型 - {type(result).__name__}，使用默认格式化")
                response = [TextContent(type="text", text=json.dumps(str(result), ensure_ascii=False, indent=2))]
            
            execution_time = time.time() - start_time
            logger.debug(f"MCPLocalAdapter.format_response: 响应格式化完成 - 耗时: {execution_time:.3f}秒, 内容块数: {len(response)}")
            return response
            
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"MCPLocalAdapter.format_response: 响应格式化失败 - 耗时: {execution_time:.3f}秒, 错误: {str(e)}", exc_info=True)
            raise
    
    def _format_single_response(self, result: ScanResult) -> Sequence[TextContent]:
        """格式化单个扫描结果"""
        logger.debug(f"MCPLocalAdapter._format_single_response: 格式化单个结果 - 扫描ID: {result.scan_id}, IP: {result.target.ip if result.target else 'N/A'}")
        
        try:
            # 创建扫描摘要
            summary = {
                "scan_id": result.scan_id,
                "target": result.target.ip,
                "status": result.status.value,
                "scan_duration": result.scan_duration,
                "summary": {
                    "open_ports_count": len(result.open_ports),
                    "http_services_count": len(result.http_services),
                    "admin_directories_count": len(result.admin_directories),
                    "admin_interfaces_count": len([d for d in result.admin_directories if d.is_admin])
                }
            }
            
            logger.debug(f"MCPLocalAdapter._format_single_response: 摘要统计 - 开放端口: {summary['summary']['open_ports_count']}, HTTP服务: {summary['summary']['http_services_count']}, 管理界面: {summary['summary']['admin_interfaces_count']}")
            
            # 开放端口信息
            open_ports = []
            for port in result.open_ports:
                open_ports.append({
                    "port": port.port,
                    "protocol": port.protocol.value,
                    "service": port.service,
                    "version": port.version,
                    "banner": port.banner,
                    "confidence": port.confidence
                })
            
            # HTTP服务信息
            http_services = []
            for http in result.http_services:
                http_services.append({
                    "url": http.url,
                    "status_code": http.status_code,
                    "title": http.title,
                    "server": http.server,
                    "technologies": http.technologies,
                    "is_https": http.is_https,
                    "response_time": http.response_time
                })
            
            # 管理目录信息
            admin_directories = []
            for directory in result.admin_directories:
                admin_directories.append({
                    "path": directory.path,
                    "status_code": directory.status_code,
                    "title": directory.title,
                    "is_admin": directory.is_admin,
                    "content_type": directory.content_type,
                    "response_time": directory.response_time
                })
            
            # 完整结果
            full_result = {
                **summary,
                "open_ports": open_ports,
                "http_services": http_services,
                "admin_directories": admin_directories
            }
            
            # 生成文本内容
            text_parts = []
            
            # 摘要信息
            text_parts.append(f"🎯 扫描摘要")
            text_parts.append(f"目标: {result.target.ip}")
            text_parts.append(f"状态: {result.status.value}")
            if result.scan_duration:
                text_parts.append(f"耗时: {result.scan_duration:.2f}秒")
            text_parts.append(f"开放端口: {len(result.open_ports)} 个")
            text_parts.append(f"HTTP服务: {len(result.http_services)} 个")
            text_parts.append(f"发现目录: {len(result.admin_directories)} 个")
            admin_count = len([d for d in result.admin_directories if d.is_admin])
            text_parts.append(f"管理界面: {admin_count} 个")
            
            # 开放端口详情
            if result.open_ports:
                text_parts.append(f"\n🔍 开放端口详情:")
                for port in result.open_ports:
                    service_info = f"{port.service}" if port.service else "unknown"
                    if port.version:
                        service_info += f" ({port.version})"
                    text_parts.append(f"  {port.port}/{port.protocol.value} - {service_info}")
            
            # HTTP服务详情
            if result.http_services:
                text_parts.append(f"\n🌐 HTTP服务详情:")
                for http in result.http_services:
                    status_info = f" [{http.status_code}]" if http.status_code else ""
                    text_parts.append(f"  {http.url}{status_info}")
                    if http.title:
                        text_parts.append(f"    标题: {http.title}")
                    if http.technologies:
                        text_parts.append(f"    技术栈: {', '.join(http.technologies)}")
            
            # 管理界面详情
            admin_interfaces = [d for d in result.admin_directories if d.is_admin]
            if admin_interfaces:
                text_parts.append(f"\n🚨 发现的管理界面:")
                for directory in admin_interfaces:
                    text_parts.append(f"  {directory.path} [{directory.status_code}]")
                    if directory.title:
                        text_parts.append(f"    标题: {directory.title}")
            
            # 返回文本内容和JSON数据
            text_content = "\n".join(text_parts)
            json_content = json.dumps(full_result, ensure_ascii=False, indent=2)
            
            logger.debug(f"MCPLocalAdapter._format_single_response: 单个结果格式化完成 - 文本长度: {len(text_content)} 字符")
            
            return [
                TextContent(type="text", text=text_content),
                TextContent(type="text", text=f"\n📊 完整JSON结果:\n{json_content}")
            ]
            
        except Exception as e:
            logger.error(f"MCPLocalAdapter._format_single_response: 单个结果格式化失败 - 扫描ID: {result.scan_id}, 错误: {str(e)}", exc_info=True)
            raise
    
    def _format_batch_response(self, results: List[ScanResult]) -> Sequence[TextContent]:
        """格式化批量扫描结果"""
        logger.debug(f"MCPLocalAdapter._format_batch_response: 格式化批量结果 - {len(results)} 个结果")
        
        try:
            text_parts = []
            
            # 批量扫描摘要
            total_hosts = len(results)
            active_hosts = len([r for r in results if r.open_ports])
            total_ports = sum(len(r.open_ports) for r in results)
            total_http = sum(len(r.http_services) for r in results)
            total_admin = sum(len([d for d in r.admin_directories if d.is_admin]) for r in results)
            
            logger.info(f"MCPLocalAdapter._format_batch_response: 批量扫描统计 - 总主机: {total_hosts}, 活跃: {active_hosts}, 端口: {total_ports}, HTTP: {total_http}, 管理界面: {total_admin}")
            
            text_parts.append(f"📊 批量扫描摘要")
            text_parts.append(f"扫描主机: {total_hosts} 个")
            text_parts.append(f"活跃主机: {active_hosts} 个")
            text_parts.append(f"开放端口: {total_ports} 个")
            text_parts.append(f"HTTP服务: {total_http} 个")
            text_parts.append(f"管理界面: {total_admin} 个")
            
            # 活跃主机详情
            if active_hosts > 0:
                text_parts.append(f"\n🎯 活跃主机详情:")
                for result in results:
                    if result.open_ports:
                        admin_count = len([d for d in result.admin_directories if d.is_admin])
                        text_parts.append(
                            f"  {result.target.ip}: "
                            f"{len(result.open_ports)}端口, "
                            f"{len(result.http_services)}HTTP, "
                            f"{admin_count}管理界面"
                        )
            
            # 发现的管理界面
            admin_hosts = []
            for result in results:
                admin_interfaces = [d for d in result.admin_directories if d.is_admin]
                if admin_interfaces:
                    admin_hosts.append({
                        "ip": result.target.ip,
                        "interfaces": admin_interfaces
                    })
            
            if admin_hosts:
                logger.info(f"MCPLocalAdapter._format_batch_response: 发现管理界面 - {len(admin_hosts)} 个主机包含管理界面")
                text_parts.append(f"\n🚨 发现的管理界面:")
                for host in admin_hosts:
                    text_parts.append(f"  {host['ip']}:")
                    for interface in host['interfaces']:
                        text_parts.append(f"    {interface.path} [{interface.status_code}]")
            
            # JSON格式的完整结果
            batch_summary = {
                "total_hosts": total_hosts,
                "active_hosts": active_hosts,
                "total_ports": total_ports,
                "total_http_services": total_http,
                "total_admin_interfaces": total_admin,
                "results": []
            }
            
            for result in results:
                if result.open_ports:  # 只包含有开放端口的主机
                    result_summary = {
                        "ip": result.target.ip,
                        "open_ports": [{"port": p.port, "service": p.service} for p in result.open_ports],
                        "http_services": [{"url": h.url, "title": h.title} for h in result.http_services],
                        "admin_interfaces": [
                            {"path": d.path, "title": d.title} 
                            for d in result.admin_directories if d.is_admin
                        ]
                    }
                    batch_summary["results"].append(result_summary)
            
            text_content = "\n".join(text_parts)
            json_content = json.dumps(batch_summary, ensure_ascii=False, indent=2)
            
            logger.debug(f"MCPLocalAdapter._format_batch_response: 批量结果格式化完成 - 文本长度: {len(text_content)} 字符, 活跃主机: {len(batch_summary['results'])}")
            
            return [
                TextContent(type="text", text=text_content),
                TextContent(type="text", text=f"\n📊 完整JSON结果:\n{json_content}")
            ]
            
        except Exception as e:
            logger.error(f"MCPLocalAdapter._format_batch_response: 批量结果格式化失败 - 结果数量: {len(results)}, 错误: {str(e)}", exc_info=True)
            raise
    
    def format_error(self, error: Exception) -> Sequence[TextContent]:
        """
        格式化错误响应
        
        Args:
            error: 异常对象
            
        Returns:
            Sequence[TextContent]: MCP错误内容
        """
        logger.error(f"MCPLocalAdapter.format_error: 格式化错误响应 - 错误类型: {type(error).__name__}, 错误信息: {str(error)}")
        
        try:
            error_info = {
                "error": True,
                "error_type": type(error).__name__,
                "error_message": str(error),
                "timestamp": datetime.now().isoformat()
            }
            
            text_content = f"❌ 扫描失败: {str(error)}"
            json_content = json.dumps(error_info, ensure_ascii=False, indent=2)
            
            logger.debug("MCPLocalAdapter.format_error: 错误响应格式化完成")
            
            return [
                TextContent(type="text", text=text_content),
                TextContent(type="text", text=f"\n📊 错误详情:\n{json_content}")
            ]
            
        except Exception as format_error:
            logger.error(f"MCPLocalAdapter.format_error: 错误响应格式化失败 - {str(format_error)}", exc_info=True)
            # 返回最基本的错误信息
            return [TextContent(type="text", text=f"❌ 系统错误: {str(error)}")]
    
    def get_active_scans_summary(self) -> Sequence[TextContent]:
        """获取活跃扫描摘要"""
        logger.debug("MCPLocalAdapter.get_active_scans_summary: 获取活跃扫描摘要")
        
        try:
            active_scans = self.service.list_active_scans()
            
            logger.info(f"MCPLocalAdapter.get_active_scans_summary: 当前活跃扫描数量: {len(active_scans)}")
            
            if not active_scans:
                logger.debug("MCPLocalAdapter.get_active_scans_summary: 没有活跃的扫描任务")
                return [TextContent(type="text", text="当前没有活跃的扫描任务")]
            
            text_parts = [f"📋 活跃扫描任务 ({len(active_scans)} 个):"]
            
            for i, scan in enumerate(active_scans):
                duration = ""
                if scan.start_time:
                    elapsed = (datetime.now() - scan.start_time).total_seconds()
                    duration = f" (已运行 {elapsed:.1f}秒)"
                
                text_parts.append(f"  {scan.scan_id[:8]}... - {scan.target.ip} - {scan.status.value}{duration}")
                logger.debug(f"MCPLocalAdapter.get_active_scans_summary: 活跃扫描 {i+1} - ID: {scan.scan_id[:8]}..., IP: {scan.target.ip}, 状态: {scan.status.value}")
            
            result_text = "\n".join(text_parts)
            logger.debug(f"MCPLocalAdapter.get_active_scans_summary: 活跃扫描摘要生成完成 - 文本长度: {len(result_text)} 字符")
            
            return [TextContent(type="text", text=result_text)]
            
        except Exception as e:
            logger.error(f"MCPLocalAdapter.get_active_scans_summary: 获取活跃扫描摘要失败 - 错误: {str(e)}", exc_info=True)
            return [TextContent(type="text", text=f"❌ 获取活跃扫描信息失败: {str(e)}")] 