"""
MCP端口扫描CLI客户端
"""

import asyncio
import click
import json
import sys
from typing import List, Optional
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.panel import Panel
from rich.text import Text
from rich import box
import time

from .models import ScanTarget, ScanConfig, ScanResult
from .service import ScanService

console = Console()


class PortScannerCLI:
    """端口扫描CLI客户端"""
    
    def __init__(self):
        self.service = ScanService()
    
    def display_scan_header(self, ip: str, config: ScanConfig) -> None:
        """显示扫描启动信息"""
        header_text = Text()
        header_text.append(f"目标: {ip}\n", style="bold blue")
        header_text.append(f"模式: 智能扫描\n", style="cyan")
        header_text.append(f"阈值: {config.smart_scan_threshold}个端口\n", style="yellow")
        header_text.append(f"策略: 少端口→全端口扫描 | 多端口→Web检测优先", style="green")
        
        console.print(Panel(
            header_text, 
            title="🧠 智能端口扫描器", 
            border_style="blue",
            box=box.ROUNDED
        ))
        console.print()
    
    def display_stage_progress(self, stage_num: int, total_stages: int, stage_name: str, details: str) -> None:
        """显示阶段进度"""
        console.print(f"🔍 [bold cyan][阶段{stage_num}/{total_stages}] {stage_name}[/bold cyan]")
        if details:
            console.print(f"├─ {details}")
        console.print("└─ 正在执行... ⚡")
        console.print()
    
    def display_stage_result(self, stage_name: str, result_text: str, duration: float = None, status: str = "success") -> None:
        """显示阶段结果"""
        status_icon = "✅" if status == "success" else "⚠️" if status == "warning" else "❌"
        console.print(f"{status_icon} [bold green]{stage_name}完成[/bold green]")
        console.print(f"├─ {result_text}")
        if duration is not None:
            console.print(f"├─ 扫描耗时: {duration:.1f}秒")
        console.print(f"└─ 状态: {status}")
        console.print()
    
    def display_smart_decision(self, decision: str, ports_count: int, threshold: int, action: str) -> None:
        """显示智能决策信息"""
        console.print(f"🧠 [bold cyan]智能决策[/bold cyan]")
        console.print(f"├─ 发现端口: [yellow]{ports_count}[/yellow]个")
        console.print(f"├─ 智能阈值: [yellow]{threshold}[/yellow]")
        console.print(f"├─ 决策逻辑: [cyan]{decision}[/cyan]")
        if action == "executed":
            console.print(f"└─ 执行动作: [green]✅ 全端口扫描[/green] (确保零遗漏)")
        else:
            console.print(f"└─ 执行动作: [red]⏭️ 跳过全端口扫描[/red] (效率优先)")
    
    async def _display_stage_completion(self, stage_name: str, scan_result, stage_duration: float) -> None:
        """显示阶段完成结果"""
        console.print("\n")  # 换行清除进度显示
        
        if stage_name == "预设端口扫描":
            ports_count = getattr(scan_result, 'preset_ports_count', 0) if scan_result else 0
            console.print(f"[bold green]✅ 预设端口扫描完成[/bold green] - 耗时 {stage_duration:.1f}秒")
            console.print(f"└─ 发现开放端口: [yellow]{ports_count}[/yellow]个")
            
            # 显示发现的端口列表（如果有的话）
            if scan_result and hasattr(scan_result, 'open_ports') and scan_result.open_ports:
                port_list = [str(p.port) for p in scan_result.open_ports[:10]]  # 最多显示10个
                if len(scan_result.open_ports) > 10:
                    port_list.append("...")
                console.print(f"   端口: [cyan]{', '.join(port_list)}[/cyan]")
        
        elif stage_name == "智能决策":
            # 智能决策阶段的特殊显示已在主逻辑中处理
            pass
        
        elif stage_name == "全端口扫描":
            new_ports = getattr(scan_result, 'full_scan_ports_count', 0) if scan_result else 0
            total_ports = len(getattr(scan_result, 'open_ports', [])) if scan_result else 0
            console.print(f"[bold green]✅ 全端口扫描完成[/bold green] - 耗时 {stage_duration:.1f}秒")
            console.print(f"├─ 新发现端口: [yellow]{new_ports}[/yellow]个")
            console.print(f"└─ 总计端口: [yellow]{total_ports}[/yellow]个")
        
        elif stage_name == "HTTP服务检测":
            http_count = len(getattr(scan_result, 'http_services', [])) if scan_result else 0
            console.print(f"[bold green]✅ HTTP服务检测完成[/bold green] - 耗时 {stage_duration:.1f}秒")
            console.print(f"└─ 发现HTTP服务: [yellow]{http_count}[/yellow]个")
            
            # 显示发现的HTTP服务URL（如果有的话）
            if scan_result and hasattr(scan_result, 'http_services') and scan_result.http_services:
                url_list = [service.url for service in scan_result.http_services[:5]]  # 最多显示5个
                if len(scan_result.http_services) > 5:
                    url_list.append("...")
                console.print(f"   服务: [cyan]{', '.join(url_list)}[/cyan]")
        
        elif stage_name == "Web探测":
            dir_count = len(getattr(scan_result, 'admin_directories', [])) if scan_result else 0
            admin_count = 0
            if scan_result and hasattr(scan_result, 'admin_directories'):
                admin_count = len([d for d in scan_result.admin_directories if d.is_admin])
            
            console.print(f"[bold green]✅ Web探测完成[/bold green] - 耗时 {stage_duration:.1f}秒")
            console.print(f"├─ 发现目录: [yellow]{dir_count}[/yellow]个")
            console.print(f"└─ 管理后台: [red]{admin_count}[/red]个")
            
            # 显示发现的管理后台（如果有的话）
            if scan_result and hasattr(scan_result, 'admin_directories') and scan_result.admin_directories:
                admin_paths = [d.path for d in scan_result.admin_directories if d.is_admin][:3]  # 最多显示3个
                if admin_paths:
                    console.print(f"   管理后台: [red]{', '.join(admin_paths)}[/red]")
        
        console.print()  # 额外换行

    async def scan_single_target(self, ip: str, ports: Optional[List[int]] = None, 
                                scan_layers: Optional[List[str]] = None,
                                config: Optional[ScanConfig] = None,
                                show_smart_info: bool = True) -> dict:
        """扫描单个目标"""
        if scan_layers is None:
            scan_layers = ["port_scan", "http_detection", "web_probe"]
        
        if config is None:
            config = ScanConfig()
        
        # 更新配置
        self.service.config = config
        
        # 显示扫描启动信息
        if show_smart_info:
            self.display_scan_header(ip, config)
        
        # 创建实时进度显示
        current_stage = None
        stage_start_time = time.time()
        result_container = {'scan_result': None}  # 使用容器来存储扫描结果
        
        async def progress_callback(stage: str, message: str):
            nonlocal current_stage, stage_start_time
            
            # 检查是否是阶段完成通知
            if message.startswith("STAGE_COMPLETE:"):
                if current_stage is not None:
                    # 解析扫描结果
                    result_str = message[len("STAGE_COMPLETE:"):]
                    stage_duration = time.time() - stage_start_time
                    
                    # 从字符串中提取结果（这里简化处理，实际可以传递对象）
                    console.print("\n")  # 换行清除进度显示
                    await self._display_stage_completion(current_stage, result_container['scan_result'], stage_duration)
                return
            
            # 检测到新阶段开始
            if stage != current_stage:
                # 开始新阶段
                current_stage = stage
                stage_start_time = time.time()
                console.print(f"\n🔄 [bold yellow]{stage}[/bold yellow] 开始...")
            
            # 显示详细进度
            # 动态更新同一行的进度信息
            progress_text = f"[yellow]⚡ {stage}[/yellow]: [cyan]{message}[/cyan]"
            console.print(f"\r{progress_text}", end="", flush=True)
        
        try:
            # 创建扫描服务
            service = ScanService(config)
            
            # 执行扫描
            scan_result = await service.scan_async_with_progress(ip, ports, scan_layers, progress_callback)
            result_container['scan_result'] = scan_result  # 更新容器中的结果
            
            # 显示最后一个阶段的完成结果
            if current_stage is not None:
                stage_duration = time.time() - stage_start_time
                await self._display_stage_completion(current_stage, scan_result, stage_duration)
            
            console.print("\n")  # 换行
            
            # 显示智能决策信息
            if show_smart_info and hasattr(scan_result, 'smart_decision') and scan_result.smart_decision:
                self.display_smart_decision(
                    scan_result.smart_decision,
                    scan_result.preset_ports_count,
                    config.smart_scan_threshold,
                    "executed" if scan_result.full_scan_executed else "skipped"
                )
                console.print()
            
            # 显示完整扫描结果
            result = self.convert_scan_result(scan_result, ip)
            self.display_scan_result(result)
            
            return result
            
        except Exception as e:
            console.print(f"\n[red]扫描失败: {e}[/red]")
            if config.log_level == "DEBUG":
                import traceback
                console.print(f"[red]{traceback.format_exc()}[/red]")
            return None
    
    def display_scan_summary(self, scan_result: ScanResult) -> None:
        """显示扫描执行摘要"""
        summary_text = Text()
        summary_text.append("📊 扫描执行摘要\n", style="bold blue")
        
        # 安全地格式化扫描时长
        preset_duration = scan_result.preset_scan_duration or 0.0
        summary_text.append(f"├─ 预设端口扫描: ✅ 完成 ({preset_duration:.1f}秒)\n", style="green")
        
        if scan_result.full_scan_executed:
            summary_text.append(f"├─ 智能决策: ✅ 执行全端口扫描 (发现额外端口)\n", style="green")
            full_duration = scan_result.full_scan_duration or 0.0
            summary_text.append(f"├─ 全端口扫描: ✅ 完成 ({full_duration:.1f}秒)\n", style="green")
        else:
            summary_text.append(f"├─ 智能决策: ✅ 跳过全端口扫描 (节省~38秒)\n", style="yellow")
        
        if scan_result.http_detection_duration:
            http_duration = scan_result.http_detection_duration or 0.0
            summary_text.append(f"├─ HTTP服务检测: ✅ 完成 ({http_duration:.1f}秒)\n", style="green")
        
        if scan_result.web_probe_duration:
            web_duration = scan_result.web_probe_duration or 0.0
            summary_text.append(f"├─ Web深度探测: ✅ 完成 ({web_duration:.1f}秒)\n", style="green")
        elif len(scan_result.http_services) == 0:
            summary_text.append(f"├─ Web深度探测: ⏭️ 跳过 (无Web服务)\n", style="cyan")
        
        total_duration = scan_result.scan_duration or 0.0
        if scan_result.full_scan_executed:
            summary_text.append(f"└─ 总耗时: {total_duration:.1f}秒", style="magenta")
        else:
            estimated_full_scan = total_duration + 35  # 估算全扫描时间
            summary_text.append(f"└─ 总耗时: {total_duration:.1f}秒 (vs 传统全扫描~{estimated_full_scan:.1f}秒)", style="magenta")
        
        console.print(Panel(summary_text, border_style="blue", box=box.ROUNDED))
        console.print()
    
    def convert_scan_result(self, scan_result: ScanResult, ip: str) -> dict:
        """转换扫描结果格式"""
        return {
            "target": ip,
            "open_ports": [
                {
                    "port": p.port,
                    "protocol": p.protocol.value,
                    "service": p.service,
                    "version": p.version,
                    "banner": p.banner
                }
                for p in scan_result.open_ports
            ],
            "http_services": [
                {
                    "url": h.url,
                    "status_code": h.status_code,
                    "title": h.title,
                    "server": h.server,
                    "technologies": h.technologies,
                    "is_https": h.is_https,
                    "response_time": h.response_time
                }
                for h in scan_result.http_services
            ],
            "admin_directories": [
                {
                    "path": d.path,
                    "status_code": d.status_code,
                    "title": d.title,
                    "is_admin": d.is_admin,
                    "content_type": d.content_type,
                    "response_time": d.response_time
                }
                for d in scan_result.admin_directories
            ],
            "scan_result": scan_result,  # 保留原始结果用于详细显示
            "summary": {
                "open_ports_count": len(scan_result.open_ports),
                "http_services_count": len(scan_result.http_services),
                "admin_directories_count": len(scan_result.admin_directories),
                "admin_interfaces_count": len([d for d in scan_result.admin_directories if d.is_admin]),
                "scan_duration": scan_result.scan_duration
            }
        }

    def display_scan_result(self, result: dict) -> None:
        """显示扫描结果"""
        scan_result = result["scan_result"]
        target = result["target"]
        summary = result["summary"]
        
        # 构建结果摘要
        summary_text = Text()
        summary_text.append(f"目标: {target}\n", style="bold blue")
        
        # 根据是否执行全端口扫描显示不同的扫描模式
        if scan_result.full_scan_executed:
            summary_text.append(f"扫描模式: 智能扫描 (少端口深度)\n", style="cyan")
        else:
            summary_text.append(f"扫描模式: 智能扫描 (多端口优化)\n", style="cyan")
        
        summary_text.append("\n", style="white")
        
        # 端口发现详情
        summary_text.append("📊 端口发现详情:\n", style="bold yellow")
        summary_text.append(f"├─ 常规扫描: {scan_result.preset_ports_count}个端口\n", style="green")
        
        if scan_result.full_scan_executed:
            if scan_result.full_scan_ports_count > 0:
                summary_text.append(f"├─ 全端口扫描: ✅ {scan_result.full_scan_ports_count}个端口\n", style="green")
            else:
                summary_text.append(f"├─ 全端口扫描: ✅ 0个新端口\n", style="green")
        else:
            summary_text.append(f"├─ 全端口扫描: ❌ 未执行 (智能跳过)\n", style="red")
        
        summary_text.append(f"└─ 总计发现: {summary['open_ports_count']}个端口\n", style="bold green")
        summary_text.append("\n", style="white")
        
        # 服务统计
        summary_text.append("🌐 服务统计:\n", style="bold cyan")
        summary_text.append(f"├─ HTTP服务: {summary['http_services_count']}个\n", style="cyan")
        summary_text.append(f"├─ 发现目录: {summary['admin_directories_count']}个\n", style="yellow")
        summary_text.append(f"└─ 管理后台: {summary['admin_interfaces_count']}个\n", style="red")
        summary_text.append("\n", style="white")
        
        # 性能统计
        summary_text.append("⏱️  性能统计:\n", style="bold magenta")
        total_duration = summary.get('scan_duration', 0.0) or 0.0
        summary_text.append(f"├─ 扫描耗时: {total_duration:.1f}秒\n", style="magenta")
        
        if scan_result.full_scan_executed:
            summary_text.append(f"└─ 智能价值: 发现高端口段服务，避免遗漏", style="magenta")
        else:
            estimated_full_scan = total_duration + 35
            efficiency = ((estimated_full_scan - total_duration) / estimated_full_scan) * 100
            summary_text.append(f"└─ 效率提升: {efficiency:.0f}% (vs 传统全扫描~{estimated_full_scan:.1f}秒)", style="magenta")
        
        console.print(Panel(
            summary_text, 
            title="🎯 扫描结果", 
            border_style="blue",
            box=box.ROUNDED
        ))
        
        # 显示开放端口
        if result["open_ports"]:
            console.print("\n[bold]开放端口:[/bold]")
            ports_table = Table(box=box.ROUNDED)
            ports_table.add_column("端口", style="cyan")
            ports_table.add_column("协议", style="green")
            ports_table.add_column("服务", style="yellow")
            ports_table.add_column("版本", style="magenta")
            
            for port in result["open_ports"]:
                ports_table.add_row(
                    str(port["port"]),
                    port["protocol"],
                    port["service"] or "unknown",
                    port["version"] or "-"
                )
            
            console.print(ports_table)
        
        # 显示HTTP服务
        if result["http_services"]:
            console.print("\n[bold]HTTP服务:[/bold]")
            http_table = Table(box=box.ROUNDED)
            http_table.add_column("URL", style="cyan")
            http_table.add_column("状态码", style="green")
            http_table.add_column("标题", style="yellow")
            http_table.add_column("服务器", style="magenta")
            
            for service in result["http_services"]:
                status_color = "green" if service["status_code"] == 200 else "yellow" if 300 <= service["status_code"] < 400 else "red"
                http_table.add_row(
                    service["url"],
                    f"[{status_color}]{service['status_code']}[/{status_color}]",
                    service["title"] or "-",
                    service["server"] or "-"
                )
            
            console.print(http_table)
        
        # 显示发现的目录
        if result["admin_directories"]:
            console.print("\n[bold]发现的目录:[/bold]")
            dir_table = Table(box=box.ROUNDED)
            dir_table.add_column("路径", style="cyan")
            dir_table.add_column("状态码", style="green")
            dir_table.add_column("标题", style="yellow")
            dir_table.add_column("管理后台", style="red")
            dir_table.add_column("响应时间", style="magenta")
            
            for directory in result["admin_directories"]:
                status_color = "green" if directory["status_code"] == 200 else "yellow"
                admin_mark = "✓" if directory["is_admin"] else "-"
                admin_color = "red" if directory["is_admin"] else "white"
                response_time = f"{directory['response_time']:.2f}s" if directory['response_time'] else "-"
                
                dir_table.add_row(
                    directory["path"],
                    f"[{status_color}]{directory['status_code']}[/{status_color}]",
                    directory["title"] or "-",
                    f"[{admin_color}]{admin_mark}[/{admin_color}]",
                    response_time
                )
            
            console.print(dir_table)


@click.group()
def cli():
    """MCP智能端口扫描工具"""
    pass


@cli.command()
@click.argument('ip')
@click.option('--ports', '-p', help='指定端口列表，用逗号分隔 (例如: 80,443,8080)')
@click.option('--layers', '-l', default='port_scan,http_detection,web_probe', 
              help='扫描层级，用逗号分隔 (默认: port_scan,http_detection,web_probe)')
@click.option('--timeout', '-t', default=3000, help='RustScan超时时间(ms)')
@click.option('--banner-timeout', default=5.0, help='Banner获取超时时间(s)')
@click.option('--http-timeout', default=10.0, help='HTTP请求超时时间(s)')
@click.option('--no-admin-scan', is_flag=True, help='禁用管理目录扫描')
@click.option('--admin-threads', default=10, help='管理目录扫描并发数')
@click.option('--output', '-o', help='输出结果到JSON文件')
@click.option('--verbose', '-v', is_flag=True, help='详细输出')
def scan(ip, ports, layers, timeout, banner_timeout, http_timeout, 
         no_admin_scan, admin_threads, output, verbose):
    """扫描单个IP地址"""
    
    # 解析参数
    port_list = None
    if ports:
        try:
            port_list = [int(p.strip()) for p in ports.split(',')]
        except ValueError:
            console.print("[red]端口格式错误，请使用逗号分隔的数字[/red]")
            sys.exit(1)
    
    scan_layers = [layer.strip() for layer in layers.split(',')]
    
    # 创建配置
    config = ScanConfig(
        rustscan_timeout=timeout,
        banner_timeout=banner_timeout,
        http_timeout=http_timeout,
        admin_scan_enabled=not no_admin_scan,
        admin_scan_threads=admin_threads,
        log_level="DEBUG" if verbose else "INFO"
    )
    
    # 执行扫描
    async def run_scan():
        cli_client = PortScannerCLI()
        result = await cli_client.scan_single_target(ip, port_list, scan_layers, config)
        
        # 保存到文件
        if output:
            with open(output, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            console.print(f"\n[green]结果已保存到: {output}[/green]")
    
    try:
        asyncio.run(run_scan())
    except KeyboardInterrupt:
        console.print("\n[yellow]扫描被用户中断[/yellow]")
    except Exception as e:
        console.print(f"[red]扫描失败: {e}[/red]")
        if verbose:
            import traceback
            console.print(traceback.format_exc())


@cli.command()
@click.argument('targets_file')
@click.option('--layers', '-l', default='port_scan,http_detection,web_probe', 
              help='扫描层级，用逗号分隔')
@click.option('--max-concurrent', '-c', default=5, help='最大并发扫描数')
@click.option('--output-dir', '-o', default='scan_results', help='输出目录')
@click.option('--verbose', '-v', is_flag=True, help='详细输出')
def batch(targets_file, layers, max_concurrent, output_dir, verbose):
    """批量扫描（从文件读取目标列表）"""
    
    try:
        # 读取目标文件
        with open(targets_file, 'r') as f:
            targets = [line.strip() for line in f if line.strip() and not line.startswith('#')]
        
        if not targets:
            console.print("[red]目标文件为空[/red]")
            sys.exit(1)
        
        console.print(f"[green]从 {targets_file} 读取到 {len(targets)} 个目标[/green]")
        
        scan_layers = [layer.strip() for layer in layers.split(',')]
        
        # 创建输出目录
        import os
        os.makedirs(output_dir, exist_ok=True)
        
        # 执行批量扫描
        async def run_batch_scan():
            cli_client = PortScannerCLI()
            semaphore = asyncio.Semaphore(max_concurrent)
            
            async def scan_target(ip):
                async with semaphore:
                    try:
                        result = await cli_client.scan_single_target(ip, None, scan_layers)
                        
                        # 保存结果
                        output_file = os.path.join(output_dir, f"scan_{ip.replace('.', '_')}.json")
                        with open(output_file, 'w', encoding='utf-8') as f:
                            json.dump(result, f, indent=2, ensure_ascii=False)
                        
                        console.print(f"[green]✓[/green] {ip} - 完成")
                        return result
                    except Exception as e:
                        console.print(f"[red]✗[/red] {ip} - 失败: {e}")
                        return None
            
            # 并发执行
            tasks = [scan_target(target) for target in targets]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 统计结果
            successful = len([r for r in results if r is not None and not isinstance(r, Exception)])
            console.print(f"\n[green]批量扫描完成: {successful}/{len(targets)} 成功[/green]")
            console.print(f"[blue]结果保存在: {output_dir}/[/blue]")
        
        asyncio.run(run_batch_scan())
        
    except FileNotFoundError:
        console.print(f"[red]目标文件不存在: {targets_file}[/red]")
    except KeyboardInterrupt:
        console.print("\n[yellow]批量扫描被用户中断[/yellow]")
    except Exception as e:
        console.print(f"[red]批量扫描失败: {e}[/red]")


@cli.command()
@click.option('--mode', default='mcp', type=click.Choice(['mcp', 'http', 'cursor']), 
              help='服务器模式：mcp(标准MCP协议) 或 http(HTTP/SSE接口) 或 cursor(Cursor优化SSE)')
@click.option('--host', default='127.0.0.1', help='HTTP/Cursor模式监听地址')
@click.option('--port', type=int, default=8080, help='HTTP/Cursor模式监听端口')
def server(mode, host, port):
    """启动MCP服务器"""
    console.print(f"[blue]启动MCP端口扫描服务器 ({mode}模式)...[/blue]")
    
    try:
        if mode == 'mcp':
            # 启动标准MCP stdio服务器
            from .mcp_server import main as mcp_main
            console.print("[green]✓[/green] 启动标准MCP协议服务器 (stdio模式)")
            asyncio.run(mcp_main())
            
        elif mode == 'http':
            # 启动HTTP/SSE桥接服务器
            from .http_sse_server import start_server
            console.print(f"[green]✓[/green] 启动HTTP/SSE桥接服务器: http://{host}:{port}")
            console.print("  支持功能:")
            console.print("  - HTTP API接口")
            console.print("  - SSE实时进度推送")  
            console.print("  - 批量扫描支持")
            console.print("  - 完全兼容现有MCP架构")
            start_server(host=host, port=port)
            
        elif mode == 'cursor':
            # 启动Cursor优化SSE服务器
            import uvicorn
            from .cursor_sse_adapter import app
            console.print(f"[green]✓[/green] 启动Cursor优化SSE服务器: http://{host}:{port}")
            console.print("  Cursor优化功能:")
            console.print("  - 实时进度SSE流")
            console.print("  - 0.5秒更新频率")
            console.print("  - 智能事件推送")
            console.print("  - 优化的数据格式")
            uvicorn.run(app, host=host, port=port, log_level="info")
            
    except KeyboardInterrupt:
        console.print("\n[yellow]服务器已停止[/yellow]")
    except Exception as e:
        console.print(f"[red]服务器启动失败: {e}[/red]")


def main():
    """主入口函数"""
    cli()


if __name__ == "__main__":
    main() 