"""
新的CLI接口
基于适配器架构的命令行界面 - 简化版
"""

import asyncio
import click
import json
from pathlib import Path
from typing import List, Optional

from ..adapters.cli_adapter import CLIAdapter
from ..service import ScanService
from ..models import ScanConfig
from ..logger_config import logger


class CLIInterface:
    """CLI接口控制器"""
    
    def __init__(self):
        # 创建优化的极速配置
        optimized_config = ScanConfig(
            rustscan_timeout=200,
            rustscan_batch_size=65535,
            rustscan_tries=1,
            rustscan_ulimit=8192,
            rustscan_ports="1-1000"
        )
        logger.debug("CLIInterface: 初始化，使用极速配置 - timeout=200ms, batch_size=65535")
        self.service = ScanService(optimized_config)
        self.adapter = CLIAdapter(self.service)
    
    async def scan_simple(self, 
                         ip: str,
                         ports: Optional[List[int]] = None,
                         output_file: Optional[str] = None,
                         quiet: bool = False) -> None:
        """执行智能扫描"""
        logger.info(f"CLIInterface: 执行扫描 - IP={ip}, ports={ports}, quiet={quiet}")
        try:
            # 显示扫描模式信息
            if not quiet:
                config = self.service.get_config()
                click.echo(f"🧠 智能扫描模式 - 阈值: {config.smart_scan_threshold}")
                click.echo(f"📊 预设端口: {config.rustscan_ports} + {len(config.preset_ports)} 个额外端口")
                click.echo(f"⚡ 智能策略: 端口少(<{config.smart_scan_threshold})→全端口扫描, 端口多→Web检测优先")
                click.echo()
            
            # 智能扫描默认使用完整层级
            layers = ["port_scan", "http_detection", "web_probe"]
            
            request_data = {
                "ip": ip,
                "ports": ports,
                "layers": layers,
                "config": {},
                "show_progress": not quiet
            }
            
            # 执行扫描
            result = await self.adapter.handle_request(request_data)
            
            # 显示结果
            self.adapter.format_response(result)
            
            # 导出结果
            if output_file:
                self.adapter.export_json(result, output_file)
                
        except Exception as e:
            self.adapter.format_error(e)


# CLI命令定义
cli_interface = CLIInterface()


@click.group()
@click.version_option("1.0.0", prog_name="智能端口扫描器")
def cli():
    """🧠 智能端口扫描器
    
    自动选择最优扫描策略，快速识别开放端口、HTTP服务和管理界面
    
    智能特性：
    • 端口少量时自动全端口扫描
    • 端口充足时优先Web服务检测
    • 无需手动选择扫描模式
    """
    pass


@cli.command()
@click.argument('target')
@click.option('-p', '--ports', help='指定端口 (例如: 80,443 或 80-90)')
@click.option('-o', '--output', help='保存结果到文件')
@click.option('-q', '--quiet', is_flag=True, help='静默模式')
@click.option('--timeout', default=3, help='超时时间(秒)', type=int)
def scan(target, ports, output, quiet, timeout):
    """🧠 智能扫描目标IP或域名
    
    智能扫描会自动选择最优扫描策略：
    • 端口数少于3个：自动全端口扫描
    • 端口数足够：优先检测Web服务，无Web服务则全端口扫描
    
    示例:
      scan 8.8.8.8                    # 智能扫描
      scan github.com                 # 自动检测Web服务
      scan 192.168.1.1 -p 80,443      # 指定端口扫描
      scan example.com -o result.json  # 智能扫描并保存结果
    """
    
    # 解析端口
    port_list = None
    if ports:
        try:
            if '-' in ports:
                # 端口范围: 80-90
                start, end = ports.split('-')
                port_list = list(range(int(start), int(end) + 1))
            else:
                # 端口列表: 80,443,8080
                port_list = [int(p.strip()) for p in ports.split(',')]
        except ValueError:
            click.echo("❌ 端口格式错误，请使用: 80,443 或 80-90", err=True)
            return
    
    # 更新超时配置
    config = ScanConfig(rustscan_timeout=timeout * 1000)
    cli_interface.service.update_config(config)
    
    if not quiet:
        click.echo(f"🧠 开始智能扫描: {target}")
    
    # 执行扫描
    asyncio.run(cli_interface.scan_simple(
        ip=target,
        ports=port_list,
        output_file=output,
        quiet=quiet
    ))


@cli.command()
@click.argument('targets_file')
@click.option('-c', '--concurrent', default=5, help='并发数', type=int)
@click.option('-o', '--output-dir', default='results', help='输出目录')
def batch(targets_file, concurrent, output_dir):
    """🧠 智能批量扫描
    
    从文件读取目标列表进行智能批量扫描
    
    示例:
      echo -e "8.8.8.8\\ngithub.com" > targets.txt
      scan batch targets.txt
    """
    
    # 读取目标文件
    try:
        with open(targets_file, 'r') as f:
            targets = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        click.echo(f"❌ 找不到文件: {targets_file}", err=True)
        return
    
    if not targets:
        click.echo("❌ 目标文件为空", err=True)
        return
    
    click.echo(f"📁 批量扫描 {len(targets)} 个目标...")
    
    # TODO: 实现批量扫描
    click.echo("批量扫描功能开发中...")


@cli.command()
@click.argument('network')
@click.option('-c', '--concurrent', default=20, help='并发数', type=int)
def network(network, concurrent):
    """🧠 智能网络段扫描
    
    对整个网络段进行智能扫描，例如: 192.168.1.0/24
    
    示例:
      scan network 192.168.1.0/24
      scan network 10.0.0.0/16 -c 50
    """
    
    try:
        import ipaddress
        net = ipaddress.IPv4Network(network, strict=False)
        host_count = len(list(net.hosts()))
        
        if host_count > 1024:
            click.echo(f"❌ 网络太大 ({host_count} 主机)，最大支持1024个", err=True)
            return
        
        if not click.confirm(f"将扫描 {host_count} 个主机，是否继续？"):
            return
        
        click.echo(f"🌐 扫描网络: {network}")
        
        # TODO: 实现网络扫描
        click.echo("网络扫描功能开发中...")
        
    except ValueError as e:
        click.echo(f"❌ 网络格式错误: {e}", err=True)


@cli.command()
def info():
    """显示扫描器信息和配置"""
    click.echo("📊 扫描器状态:")
    
    current_config = cli_interface.service.get_config()
    active_scans = cli_interface.service.list_active_scans()
    
    click.echo(f"  • 活跃扫描: {len(active_scans)} 个")
    click.echo(f"  • 超时时间: {current_config.rustscan_timeout/1000:.1f}秒")
    click.echo(f"  • HTTP超时: {current_config.http_timeout:.1f}秒")
    click.echo(f"  • 管理扫描: {'启用' if current_config.admin_scan_enabled else '禁用'}")
    
    if active_scans:
        click.echo("\n活跃扫描:")
        for scan in active_scans:
            click.echo(f"  • {scan.target.ip} - {scan.status.value}")


@cli.command()
@click.option('--rustscan-timeout', type=int, help='RustScan超时(毫秒)')
@click.option('--http-timeout', type=float, help='HTTP超时(秒)')
@click.option('--admin-scan/--no-admin-scan', default=None, help='启用/禁用管理扫描')
def config(rustscan_timeout, http_timeout, admin_scan):
    """配置扫描器参数
    
    示例:
      scan config --rustscan-timeout 5000
      scan config --http-timeout 15.0
      scan config --no-admin-scan
    """
    
    current_config = cli_interface.service.get_config()
    updates = {}
    
    if rustscan_timeout is not None:
        updates['rustscan_timeout'] = rustscan_timeout
        click.echo(f"✓ RustScan超时更新为: {rustscan_timeout}ms")
    
    if http_timeout is not None:
        updates['http_timeout'] = http_timeout
        click.echo(f"✓ HTTP超时更新为: {http_timeout}s")
    
    if admin_scan is not None:
        updates['admin_scan_enabled'] = admin_scan
        status = "启用" if admin_scan else "禁用"
        click.echo(f"✓ 管理扫描: {status}")
    
    if updates:
        # 更新配置
        try:
            config_dict = current_config.model_dump()
        except AttributeError:
            config_dict = current_config.dict()
        config_dict.update(updates)
        new_config = ScanConfig(**config_dict)
        cli_interface.service.update_config(new_config)
    else:
        # 显示当前配置
        click.echo("当前配置:")
        click.echo(f"  RustScan超时: {current_config.rustscan_timeout}ms")
        click.echo(f"  HTTP超时: {current_config.http_timeout}s")
        click.echo(f"  管理扫描: {'启用' if current_config.admin_scan_enabled else '禁用'}")


def main():
    """CLI入口点"""
    cli()


if __name__ == '__main__':
    main() 