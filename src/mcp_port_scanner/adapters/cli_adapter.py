"""
CLI适配器
处理命令行接口的请求和响应格式化
"""

import json
from typing import Any, Dict, List, Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.progress import Progress, SpinnerColumn, TextColumn

from . import BaseAdapter
from ..service import ScanService, ScanProgress
from ..models import ScanResult, ScanConfig, ScanTarget


class CLIAdapter(BaseAdapter):
    """CLI适配器"""
    
    def __init__(self, service: Optional[ScanService] = None):
        self.service = service or ScanService()
        self.console = Console()
    
    async def handle_request(self, request_data: Dict[str, Any]) -> ScanResult:
        """
        处理CLI请求
        
        Args:
            request_data: 请求数据
                - ip: 目标IP
                - ports: 端口列表（可选）
                - layers: 扫描层级（可选）
                - config: 扫描配置（可选）
                - show_progress: 是否显示进度（可选）
                
        Returns:
            ScanResult: 扫描结果
        """
        ip = request_data["ip"]
        ports = request_data.get("ports")
        layers = request_data.get("layers", ["port_scan", "http_detection", "web_probe"])
        config_data = request_data.get("config", {})
        show_progress = request_data.get("show_progress", True)
        
        # 更新配置
        if config_data:
            current_config = self.service.get_config()
            config_dict = current_config.dict()
            config_dict.update(config_data)
            new_config = ScanConfig(**config_dict)
            self.service.update_config(new_config)
        
        # 显示扫描开始信息
        self.console.print(f"[bold blue]🚀 开始扫描目标: {ip}[/bold blue]")
        
        if show_progress:
            # 使用进度条显示智能扫描过程
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=self.console
            ) as progress:
                
                # 使用智能扫描特定的进度反馈
                scan_task = progress.add_task("🧠 智能扫描中...", total=None)
                
                async def progress_callback(stage: str, detail: str = ""):
                    """智能扫描进度回调"""
                    description = f"🧠 {stage}"
                    if detail:
                        description += f" - {detail}"
                    progress.update(scan_task, description=description)
                
                # 执行扫描，传入进度回调
                result = await self.service.scan_async_with_progress(ip, ports, layers, progress_callback)
                
                # 完成任务
                progress.update(scan_task, description="✅ 智能扫描完成", completed=True)
        else:
            # 直接执行扫描
            result = await self.service.scan_async(ip, ports, layers)
        
        return result
    
    def format_response(self, result: ScanResult) -> None:
        """
        格式化CLI响应并显示
        
        Args:
            result: 扫描结果
        """
        target_ip = result.target.ip
        
        # 显示摘要信息
        self._display_summary(target_ip, result)
        
        # 显示开放端口
        if result.open_ports:
            self._display_ports(result.open_ports)
        
        # 显示HTTP服务
        if result.http_services:
            self._display_http_services(result.http_services)
        
        # 显示管理目录
        if result.admin_directories:
            self._display_admin_directories(result.admin_directories)
    
    def format_error(self, error: Exception) -> None:
        """
        格式化错误信息并显示
        
        Args:
            error: 异常对象
        """
        self.console.print(f"[bold red]扫描失败: {str(error)}[/bold red]")
    
    def _display_summary(self, target_ip: str, result: ScanResult) -> None:
        """显示扫描摘要"""
        summary_text = Text()
        summary_text.append(f"目标: {target_ip}\n", style="bold blue")
        summary_text.append(f"开放端口: {len(result.open_ports)}\n", style="green")
        summary_text.append(f"HTTP服务: {len(result.http_services)}\n", style="cyan")
        summary_text.append(f"发现目录: {len(result.admin_directories)}\n", style="yellow")
        
        admin_count = len([d for d in result.admin_directories if d.is_admin])
        summary_text.append(f"管理界面: {admin_count}", style="red")
        
        if result.scan_duration:
            summary_text.append(f"\n扫描耗时: {result.scan_duration:.2f}秒", style="dim")
        
        self.console.print(Panel(summary_text, title="扫描摘要", border_style="blue"))
    
    def _display_ports(self, port_infos) -> None:
        """显示开放端口表格"""
        self.console.print("\n[bold]开放端口:[/bold]")
        
        table = Table()
        table.add_column("端口", style="cyan", width=8)
        table.add_column("协议", style="green", width=8)
        table.add_column("服务", style="yellow", width=15)
        table.add_column("版本", style="magenta", width=20)
        table.add_column("置信度", style="blue", width=10)
        table.add_column("Banner", style="dim", max_width=40)
        
        for port in port_infos:
            confidence_color = "green" if port.confidence > 0.7 else "yellow" if port.confidence > 0.4 else "red"
            confidence_text = f"[{confidence_color}]{port.confidence:.2f}[/{confidence_color}]"
            
            # 截断Banner显示
            banner = port.banner or ""
            if len(banner) > 40:
                banner = banner[:37] + "..."
            banner = banner.replace('\n', '\\n').replace('\r', '\\r')
            
            table.add_row(
                str(port.port),
                port.protocol.value,
                port.service or "unknown",
                port.version or "",
                confidence_text,
                banner
            )
        
        self.console.print(table)
    
    def _display_http_services(self, http_services) -> None:
        """显示HTTP服务表格"""
        self.console.print("\n[bold]HTTP服务:[/bold]")
        
        table = Table()
        table.add_column("URL", style="cyan", width=30)
        table.add_column("状态", style="green", width=8)
        table.add_column("标题", style="yellow", width=25)
        table.add_column("服务器", style="magenta", width=20)
        table.add_column("技术栈", style="blue", width=20)
        table.add_column("响应时间", style="dim", width=10)
        
        for http in http_services:
            # 状态码颜色
            status_color = "green" if http.status_code and http.status_code < 400 else "red"
            status_text = f"[{status_color}]{http.status_code or 'N/A'}[/{status_color}]"
            
            # 截断标题和服务器信息
            title = http.title or ""
            if len(title) > 25:
                title = title[:22] + "..."
            
            server = http.server or ""
            if len(server) > 20:
                server = server[:17] + "..."
            
            # 技术栈
            tech_stack = ", ".join(http.technologies[:3]) if http.technologies else ""
            if len(tech_stack) > 20:
                tech_stack = tech_stack[:17] + "..."
            
            # 响应时间
            response_time = f"{http.response_time:.2f}s" if http.response_time else ""
            
            table.add_row(
                http.url,
                status_text,
                title,
                server,
                tech_stack,
                response_time
            )
        
        self.console.print(table)
    
    def _display_admin_directories(self, admin_directories) -> None:
        """显示管理目录表格"""
        self.console.print("\n[bold]发现的目录:[/bold]")
        
        table = Table()
        table.add_column("路径", style="cyan", width=30)
        table.add_column("状态", style="green", width=8)
        table.add_column("类型", style="yellow", width=12)
        table.add_column("标题", style="magenta", width=25)
        table.add_column("内容类型", style="blue", width=15)
        table.add_column("响应时间", style="dim", width=10)
        
        for directory in admin_directories:
            # 状态码颜色
            status_color = "green" if directory.status_code < 400 else "red"
            status_text = f"[{status_color}]{directory.status_code}[/{status_color}]"
            
            # 是否为管理界面
            admin_type = "[red]管理界面[/red]" if directory.is_admin else "普通目录"
            
            # 截断标题
            title = directory.title or ""
            if len(title) > 25:
                title = title[:22] + "..."
            
            # 内容类型
            content_type = directory.content_type or ""
            if len(content_type) > 15:
                content_type = content_type[:12] + "..."
            
            # 响应时间
            response_time = f"{directory.response_time:.2f}s" if directory.response_time else ""
            
            table.add_row(
                directory.path,
                status_text,
                admin_type,
                title,
                content_type,
                response_time
            )
        
        self.console.print(table)
    
    def export_json(self, result: ScanResult, filename: str) -> None:
        """
        导出结果为JSON文件
        
        Args:
            result: 扫描结果
            filename: 文件名
        """
        try:
            # 转换为可序列化的字典
            result_dict = {
                "scan_id": result.scan_id,
                "target": {
                    "ip": result.target.ip,
                    "ports": result.target.ports
                },
                "status": result.status.value,
                "start_time": result.start_time.isoformat() if result.start_time else None,
                "end_time": result.end_time.isoformat() if result.end_time else None,
                "scan_duration": result.scan_duration,
                "open_ports": [
                    {
                        "port": p.port,
                        "protocol": p.protocol.value,
                        "state": p.state,
                        "service": p.service,
                        "version": p.version,
                        "banner": p.banner,
                        "confidence": p.confidence
                    }
                    for p in result.open_ports
                ],
                "http_services": [
                    {
                        "url": h.url,
                        "status_code": h.status_code,
                        "title": h.title,
                        "server": h.server,
                        "headers": h.headers,
                        "technologies": h.technologies,
                        "is_https": h.is_https,
                        "redirect_url": h.redirect_url,
                        "content_length": h.content_length,
                        "response_time": h.response_time
                    }
                    for h in result.http_services
                ],
                "admin_directories": [
                    {
                        "path": d.path,
                        "status_code": d.status_code,
                        "content_length": d.content_length,
                        "content_type": d.content_type,
                        "title": d.title,
                        "is_admin": d.is_admin,
                        "response_time": d.response_time
                    }
                    for d in result.admin_directories
                ],
                "summary": {
                    "open_ports_count": result.open_ports_count,
                    "http_services_count": result.http_services_count,
                    "admin_directories_count": len(result.admin_directories),
                    "admin_interfaces_count": len([d for d in result.admin_directories if d.is_admin])
                }
            }
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(result_dict, f, indent=2, ensure_ascii=False)
            
            self.console.print(f"[green]结果已导出到: {filename}[/green]")
            
        except Exception as e:
            self.console.print(f"[red]导出失败: {str(e)}[/red]")
    
    def display_batch_summary(self, results: List[ScanResult]) -> None:
        """
        显示批量扫描摘要
        
        Args:
            results: 扫描结果列表
        """
        self.console.print("\n[bold]批量扫描摘要:[/bold]")
        
        table = Table()
        table.add_column("目标IP", style="cyan", width=15)
        table.add_column("状态", style="green", width=10)
        table.add_column("开放端口", style="yellow", width=10)
        table.add_column("HTTP服务", style="magenta", width=10)
        table.add_column("管理界面", style="red", width=10)
        table.add_column("耗时", style="dim", width=10)
        
        total_hosts = len(results)
        active_hosts = 0
        total_ports = 0
        total_http = 0
        total_admin = 0
        
        for result in results:
            if result.open_ports:
                active_hosts += 1
            
            total_ports += len(result.open_ports)
            total_http += len(result.http_services)
            admin_count = len([d for d in result.admin_directories if d.is_admin])
            total_admin += admin_count
            
            # 状态颜色
            if result.status.value == "completed":
                status_color = "green" if result.open_ports else "dim"
                status_text = f"[{status_color}]完成[/{status_color}]"
            elif result.status.value == "failed":
                status_text = "[red]失败[/red]"
            else:
                status_text = "[yellow]运行中[/yellow]"
            
            duration = f"{result.scan_duration:.1f}s" if result.scan_duration else ""
            
            table.add_row(
                result.target.ip,
                status_text,
                str(len(result.open_ports)),
                str(len(result.http_services)),
                str(admin_count),
                duration
            )
        
        self.console.print(table)
        
        # 显示统计信息
        stats_text = Text()
        stats_text.append(f"总计扫描: {total_hosts} 个主机\n", style="bold")
        stats_text.append(f"活跃主机: {active_hosts} 个\n", style="green")
        stats_text.append(f"开放端口: {total_ports} 个\n", style="yellow")
        stats_text.append(f"HTTP服务: {total_http} 个\n", style="cyan")
        stats_text.append(f"管理界面: {total_admin} 个", style="red")
        
        self.console.print(Panel(stats_text, title="统计信息", border_style="blue")) 