"""
MCP本地适配器
处理基于stdio的MCP协议请求和响应
"""

import json
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
        self.service = service or ScanService()
        logger.debug("MCPLocalAdapter: 初始化完成")
    
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
        tool_name = request_data.get("tool_name")
        arguments = request_data.get("arguments", {})
        
        if tool_name == "scan_target":
            return await self._handle_scan_target(arguments)
        elif tool_name == "batch_scan":
            return await self._handle_batch_scan(arguments)
        elif tool_name == "get_scan_status":
            return await self._handle_get_scan_status(arguments)
        elif tool_name == "get_scan_result":
            return await self._handle_get_scan_result(arguments)
        else:
            raise ValueError(f"不支持的工具: {tool_name}")
    
    async def _handle_scan_target(self, arguments: Dict[str, Any]) -> ScanResult:
        """处理单目标扫描"""
        ip = arguments["ip"]
        ports = arguments.get("ports")
        scan_layers = arguments.get("scan_layers", ["port_scan", "http_detection", "web_probe"])
        config_dict = arguments.get("config", {})
        
        logger.info(f"MCPLocalAdapter: 处理单目标扫描请求 - IP={ip}, ports={ports}")
        
        # 更新配置
        if config_dict:
            current_config = self.service.get_config()
            config_data = current_config.dict()
            config_data.update(config_dict)
            new_config = ScanConfig(**config_data)
            self.service.update_config(new_config)
        
        # 执行扫描
        result = await self.service.scan_async(ip, ports, scan_layers)
        return result
    
    async def _handle_batch_scan(self, arguments: Dict[str, Any]) -> List[ScanResult]:
        """处理批量扫描"""
        targets_data = arguments["targets"]
        scan_layers = arguments.get("scan_layers", ["port_scan", "http_detection", "web_probe"])
        max_concurrent = arguments.get("max_concurrent", 5)
        
        logger.info(f"MCPLocalAdapter: 处理批量扫描请求 - {len(targets_data)}个目标, 并发数={max_concurrent}")
        
        # 转换目标格式
        targets = []
        for target_data in targets_data:
            target = ScanTarget(
                ip=target_data["ip"],
                ports=target_data.get("ports")
            )
            targets.append(target)
        
        # 执行批量扫描
        results = await self.service.batch_scan_async(targets, scan_layers, max_concurrent)
        return results
    
    async def _handle_get_scan_status(self, arguments: Dict[str, Any]) -> Optional[ScanResult]:
        """获取扫描状态"""
        scan_id = arguments["scan_id"]
        return self.service.get_scan_status(scan_id)
    
    async def _handle_get_scan_result(self, arguments: Dict[str, Any]) -> Optional[ScanResult]:
        """获取扫描结果"""
        scan_id = arguments["scan_id"]
        return self.service.get_scan_result(scan_id)
    
    def format_response(self, result: Any) -> Sequence[TextContent]:
        """
        格式化MCP响应
        
        Args:
            result: 扫描结果或结果列表
            
        Returns:
            Sequence[TextContent]: MCP文本内容列表
        """
        if isinstance(result, list):
            # 批量扫描结果
            return self._format_batch_response(result)
        elif isinstance(result, ScanResult):
            # 单个扫描结果
            return self._format_single_response(result)
        elif result is None:
            return [TextContent(type="text", text="未找到请求的扫描结果")]
        else:
            return [TextContent(type="text", text=json.dumps(str(result), ensure_ascii=False, indent=2))]
    
    def _format_single_response(self, result: ScanResult) -> Sequence[TextContent]:
        """格式化单个扫描结果"""
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
        
        return [
            TextContent(type="text", text=text_content),
            TextContent(type="text", text=f"\n📊 完整JSON结果:\n{json_content}")
        ]
    
    def _format_batch_response(self, results: List[ScanResult]) -> Sequence[TextContent]:
        """格式化批量扫描结果"""
        text_parts = []
        
        # 批量扫描摘要
        total_hosts = len(results)
        active_hosts = len([r for r in results if r.open_ports])
        total_ports = sum(len(r.open_ports) for r in results)
        total_http = sum(len(r.http_services) for r in results)
        total_admin = sum(len([d for d in r.admin_directories if d.is_admin]) for r in results)
        
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
        
        return [
            TextContent(type="text", text=text_content),
            TextContent(type="text", text=f"\n📊 完整JSON结果:\n{json_content}")
        ]
    
    def format_error(self, error: Exception) -> Sequence[TextContent]:
        """
        格式化错误响应
        
        Args:
            error: 异常对象
            
        Returns:
            Sequence[TextContent]: MCP错误内容
        """
        error_info = {
            "error": True,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "timestamp": datetime.now().isoformat()
        }
        
        text_content = f"❌ 扫描失败: {str(error)}"
        json_content = json.dumps(error_info, ensure_ascii=False, indent=2)
        
        return [
            TextContent(type="text", text=text_content),
            TextContent(type="text", text=f"\n📊 错误详情:\n{json_content}")
        ]
    
    def get_active_scans_summary(self) -> Sequence[TextContent]:
        """获取活跃扫描摘要"""
        active_scans = self.service.list_active_scans()
        
        if not active_scans:
            return [TextContent(type="text", text="当前没有活跃的扫描任务")]
        
        text_parts = [f"📋 活跃扫描任务 ({len(active_scans)} 个):"]
        
        for scan in active_scans:
            duration = ""
            if scan.start_time:
                elapsed = (datetime.now() - scan.start_time).total_seconds()
                duration = f" (已运行 {elapsed:.1f}秒)"
            
            text_parts.append(f"  {scan.scan_id[:8]}... - {scan.target.ip} - {scan.status.value}{duration}")
        
        return [TextContent(type="text", text="\n".join(text_parts))] 