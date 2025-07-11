#!/usr/bin/env python3
"""
MCP端口扫描服务简单测试示例
"""

import asyncio
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from mcp_port_scanner.models import ScanTarget, ScanConfig
from mcp_port_scanner.scanner import PortScanner
from mcp_port_scanner.http_detector import HTTPDetector
from mcp_port_scanner.web_prober import WebProber


async def test_local_scan():
    """测试本地扫描"""
    print("🚀 开始测试MCP端口扫描服务")
    print("=" * 50)
    
    # 创建配置
    config = ScanConfig(
        rustscan_timeout=1000,  # 较短的超时时间用于测试
        banner_timeout=3.0,
        http_timeout=5.0,
        admin_scan_enabled=True,
        admin_scan_threads=5,
        log_level="INFO"
    )
    
    # 创建扫描目标（本地回环地址）
    target = ScanTarget(ip="127.0.0.1")
    
    try:
        # 第一层：端口扫描
        print("\n📡 第一层：端口扫描")
        print("-" * 30)
        scanner = PortScanner(config)
        port_infos = await scanner.scan_target(target)
        
        print(f"发现 {len(port_infos)} 个开放端口:")
        for port_info in port_infos:
            confidence_emoji = "🟢" if port_info.confidence > 0.7 else "🟡" if port_info.confidence > 0.4 else "🔴"
            print(f"  {confidence_emoji} {port_info.port}/{port_info.protocol.value} - "
                  f"{port_info.service or 'unknown'} "
                  f"(置信度: {port_info.confidence:.2f})")
            if port_info.banner:
                print(f"     Banner: {port_info.banner[:80]}...")
        
        if not port_infos:
            print("  ⚠️  没有发现开放端口，可能需要启动一些本地服务进行测试")
            return
        
        # 第二层：HTTP服务检测
        print("\n🌐 第二层：HTTP服务检测")
        print("-" * 30)
        http_detector = HTTPDetector(config)
        http_services = await http_detector.detect_http_services(target.ip, port_infos)
        
        if http_services:
            print(f"发现 {len(http_services)} 个HTTP服务:")
            for http_service in http_services:
                status_emoji = "✅" if http_service.status_code == 200 else "⚠️"
                print(f"  {status_emoji} {http_service.url}")
                print(f"     状态码: {http_service.status_code}")
                print(f"     标题: {http_service.title or 'N/A'}")
                print(f"     服务器: {http_service.server or 'N/A'}")
                if http_service.technologies:
                    print(f"     技术栈: {', '.join(http_service.technologies)}")
                print(f"     响应时间: {http_service.response_time:.2f}s")
        else:
            print("  ℹ️  没有发现HTTP服务")
        
        # 第三层：Web深度探测
        if http_services:
            print("\n🔍 第三层：Web深度探测")
            print("-" * 30)
            web_prober = WebProber(config)
            admin_directories = await web_prober.probe_web_services(http_services)
            
            if admin_directories:
                print(f"发现 {len(admin_directories)} 个目录:")
                for directory in admin_directories:
                    admin_emoji = "🔑" if directory.is_admin else "📁"
                    status_color = "🟢" if directory.status_code == 200 else "🟡" if 300 <= directory.status_code < 400 else "🔴"
                    print(f"  {admin_emoji} {directory.path} - {status_color} {directory.status_code}")
                    if directory.title:
                        print(f"     标题: {directory.title}")
                    if directory.is_admin:
                        print(f"     ⚠️  可能是管理界面!")
            else:
                print("  ℹ️  没有发现有趣的目录")
        
        print("\n🎉 测试完成!")
        print(f"📊 扫描摘要:")
        print(f"   开放端口: {len(port_infos)}")
        print(f"   HTTP服务: {len(http_services)}")
        if http_services:
            admin_count = len([d for d in admin_directories if d.is_admin])
            print(f"   发现目录: {len(admin_directories)}")
            print(f"   管理界面: {admin_count}")
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


async def test_external_target():
    """测试外部目标（需要谨慎使用）"""
    print("\n🌍 测试外部目标")
    print("=" * 50)
    
    # 使用一些公开的测试目标
    test_targets = [
        "httpbin.org",  # HTTP测试服务
        "example.com",  # 示例域名
    ]
    
    config = ScanConfig(
        rustscan_timeout=2000,
        banner_timeout=5.0,
        http_timeout=10.0,
        admin_scan_enabled=False,  # 对外部目标禁用管理目录扫描
        log_level="INFO"
    )
    
    for target_ip in test_targets:
        print(f"\n🎯 测试目标: {target_ip}")
        print("-" * 30)
        
        try:
            target = ScanTarget(ip=target_ip, ports=[80, 443])  # 只扫描Web端口
            
            scanner = PortScanner(config)
            port_infos = await scanner.scan_target(target)
            
            if port_infos:
                print(f"发现 {len(port_infos)} 个开放端口")
                
                http_detector = HTTPDetector(config)
                http_services = await http_detector.detect_http_services(target_ip, port_infos)
                
                if http_services:
                    print(f"发现 {len(http_services)} 个HTTP服务:")
                    for http_service in http_services:
                        print(f"  ✅ {http_service.url} - {http_service.title or 'No title'}")
            else:
                print("  没有发现开放端口")
                
        except Exception as e:
            print(f"  ❌ 扫描失败: {e}")


def print_banner():
    """打印横幅"""
    banner = """
    ███╗   ███╗ ██████╗██████╗     ██████╗  ██████╗ ██████╗ ████████╗    ███████╗ ██████╗ █████╗ ███╗   ██╗
    ████╗ ████║██╔════╝██╔══██╗    ██╔══██╗██╔═══██╗██╔══██╗╚══██╔══╝    ██╔════╝██╔════╝██╔══██╗████╗  ██║
    ██╔████╔██║██║     ██████╔╝    ██████╔╝██║   ██║██████╔╝   ██║       ███████╗██║     ███████║██╔██╗ ██║
    ██║╚██╔╝██║██║     ██╔═══╝     ██╔═══╝ ██║   ██║██╔══██╗   ██║       ╚════██║██║     ██╔══██║██║╚██╗██║
    ██║ ╚═╝ ██║╚██████╗██║         ██║     ╚██████╔╝██║  ██║   ██║       ███████║╚██████╗██║  ██║██║ ╚████║
    ╚═╝     ╚═╝ ╚═════╝╚═╝         ╚═╝      ╚═════╝ ╚═╝  ╚═╝   ╚═╝       ╚══════╝ ╚═════╝╚═╝  ╚═╝╚═╝  ╚═══╝
    
    🚀 MCP智能分层端口扫描服务测试
    📡 第一层：RustScan端口扫描 + Banner获取
    🌐 第二层：智能HTTP服务识别
    🔍 第三层：Web深度探测 + 管理目录扫描
    """
    print(banner)


async def main():
    """主函数"""
    print_banner()
    
    print("请选择测试模式:")
    print("1. 本地扫描测试 (127.0.0.1)")
    print("2. 外部目标测试 (httpbin.org, example.com)")
    print("3. 全部测试")
    
    try:
        choice = input("\n请输入选择 (1-3): ").strip()
        
        if choice == "1":
            await test_local_scan()
        elif choice == "2":
            await test_external_target()
        elif choice == "3":
            await test_local_scan()
            await test_external_target()
        else:
            print("❌ 无效选择")
            return
            
    except KeyboardInterrupt:
        print("\n\n⚠️  测试被用户中断")
    except Exception as e:
        print(f"\n❌ 测试过程中发生错误: {e}")


if __name__ == "__main__":
    asyncio.run(main()) 