"""
MCP端口扫描服务器
基于官方MCP Python SDK实现
"""

import asyncio
import uuid
import json
import os
from typing import Dict, List, Any, Optional, Sequence
from datetime import datetime

from mcp.server import Server
from mcp.types import Tool, TextContent
from mcp.server.stdio import stdio_server
from loguru import logger

from .models import (
    ScanTarget, ScanConfig, ScanRequest, ScanResponse, 
    ScanResult, ScanStatus
)
from .scanner import PortScanner
from .http_detector import HTTPDetector
from .web_prober import WebProber

# 创建服务器实例
server = Server("port-scanner")

# 全局状态管理
active_scans: Dict[str, ScanResult] = {}
scanner = PortScanner()
http_detector = HTTPDetector()
web_prober = WebProber()

# 设置日志 - 检查是否在docker run模式下
if os.path.exists("/app/logs"):
    # docker compose模式，可以写入文件
    logger.add(
        "logs/mcp_server_{time}.log",
        level="INFO",
        rotation="1 day",
        retention="7 days"
    )
else:
    # docker run模式，只输出到stderr
    logger.remove()
    logger.add(lambda msg: None, level="INFO")  # 禁用日志输出，避免干扰MCP协议

@server.list_tools()
async def list_tools() -> List[Tool]:
    """列出可用的工具"""
    return [
        Tool(
            name="scan_target",
            description="对单个IP地址进行分层递进端口扫描",
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
                        "description": "指定端口列表（可选，默认扫描常规1000端口）"
                    },
                    "scan_layers": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "扫描层级（可选）",
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
            name="list_active_scans",
            description="列出所有活跃的扫描任务",
            inputSchema={
                "type": "object",
                "properties": {}
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
        )
    ]

@server.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> Sequence[TextContent]:
    """调用工具"""
    try:
        if name == "scan_target":
            return await handle_scan_target(arguments)
        elif name == "batch_scan":
            return await handle_batch_scan(arguments)
        elif name == "get_scan_status":
            return await handle_get_scan_status(arguments)
        elif name == "list_active_scans":
            return await handle_list_active_scans(arguments)
        elif name == "get_scan_result":
            return await handle_get_scan_result(arguments)
        else:
            return [TextContent(type="text", text=f"未知工具: {name}")]
    except Exception as e:
        logger.error(f"工具调用失败 {name}: {e}")
        return [TextContent(type="text", text=f"工具调用失败: {str(e)}")]

async def handle_scan_target(arguments: Dict[str, Any]) -> Sequence[TextContent]:
    """处理单个目标扫描"""
    ip = arguments["ip"]
    ports = arguments.get("ports")
    scan_layers = arguments.get("scan_layers", ["port_scan", "http_detection", "web_probe"])
    config_dict = arguments.get("config", {})
    
    # 创建扫描配置
    config = ScanConfig(**config_dict)
    
    # 创建扫描目标
    target = ScanTarget(ip=ip, ports=ports)
    
    # 生成扫描ID
    scan_id = str(uuid.uuid4())
    
    # 创建扫描结果对象
    scan_result = ScanResult(
        target=target,
        scan_id=scan_id,
        status=ScanStatus.RUNNING
    )
    
    # 保存到活跃扫描列表
    active_scans[scan_id] = scan_result
    
    logger.info(f"开始扫描目标 {ip}，扫描ID: {scan_id}")
    
    # 异步执行扫描
    asyncio.create_task(execute_scan(scan_result, scan_layers, config))
    
    response = {
        "scan_id": scan_id,
        "status": "running",
        "message": f"已启动对 {ip} 的扫描",
        "target": ip,
        "scan_layers": scan_layers
    }
    
    return [TextContent(type="text", text=json.dumps(response, indent=2, ensure_ascii=False))]

async def handle_batch_scan(arguments: Dict[str, Any]) -> Sequence[TextContent]:
    """处理批量扫描"""
    targets_data = arguments["targets"]
    scan_layers = arguments.get("scan_layers", ["port_scan", "http_detection", "web_probe"])
    max_concurrent = arguments.get("max_concurrent", 5)
    
    scan_results = []
    
    for target_data in targets_data:
        ip = target_data["ip"]
        ports = target_data.get("ports")
        
        target = ScanTarget(ip=ip, ports=ports)
        scan_id = str(uuid.uuid4())
        
        scan_result = ScanResult(
            target=target,
            scan_id=scan_id,
            status=ScanStatus.PENDING
        )
        
        active_scans[scan_id] = scan_result
        scan_results.append(scan_result)
    
    logger.info(f"开始批量扫描，共 {len(scan_results)} 个目标")
    
    # 异步执行批量扫描
    asyncio.create_task(execute_batch_scan(scan_results, scan_layers, max_concurrent))
    
    response = {
        "batch_scan_id": str(uuid.uuid4()),
        "targets_count": len(scan_results),
        "scan_ids": [result.scan_id for result in scan_results],
        "status": "running",
        "max_concurrent": max_concurrent
    }
    
    return [TextContent(type="text", text=json.dumps(response, indent=2, ensure_ascii=False))]

async def handle_get_scan_status(arguments: Dict[str, Any]) -> Sequence[TextContent]:
    """获取扫描状态"""
    scan_id = arguments["scan_id"]
    
    if scan_id not in active_scans:
        return [TextContent(type="text", text=f"扫描ID {scan_id} 不存在")]
    
    scan_result = active_scans[scan_id]
    
    status_info = {
        "scan_id": scan_id,
        "status": scan_result.status.value,
        "target": scan_result.target.ip,
        "start_time": scan_result.start_time.isoformat(),
        "end_time": scan_result.end_time.isoformat() if scan_result.end_time else None,
        "open_ports_count": scan_result.open_ports_count,
        "http_services_count": scan_result.http_services_count,
        "admin_directories_count": len(scan_result.admin_directories),
        "scan_duration": scan_result.scan_duration,
        "error_message": scan_result.error_message
    }
    
    return [TextContent(type="text", text=json.dumps(status_info, indent=2, ensure_ascii=False))]

async def handle_list_active_scans(arguments: Dict[str, Any]) -> Sequence[TextContent]:
    """列出活跃扫描"""
    active_scans_list = []
    
    for scan_id, scan_result in active_scans.items():
        scan_info = {
            "scan_id": scan_id,
            "status": scan_result.status.value,
            "target": scan_result.target.ip,
            "start_time": scan_result.start_time.isoformat(),
            "duration": scan_result.scan_duration
        }
        active_scans_list.append(scan_info)
    
    response = {
        "active_scans_count": len(active_scans_list),
        "scans": active_scans_list
    }
    
    return [TextContent(type="text", text=json.dumps(response, indent=2, ensure_ascii=False))]

async def handle_get_scan_result(arguments: Dict[str, Any]) -> Sequence[TextContent]:
    """获取扫描结果"""
    scan_id = arguments["scan_id"]
    
    if scan_id not in active_scans:
        return [TextContent(type="text", text=f"扫描ID {scan_id} 不存在")]
    
    scan_result = active_scans[scan_id]
    
    # 构建详细结果
    result_data = {
        "scan_id": scan_id,
        "status": scan_result.status.value,
        "target": {
            "ip": scan_result.target.ip,
            "ports": scan_result.target.ports
        },
        "timing": {
            "start_time": scan_result.start_time.isoformat(),
            "end_time": scan_result.end_time.isoformat() if scan_result.end_time else None,
            "duration": scan_result.scan_duration
        },
        "summary": {
            "total_ports_scanned": scan_result.total_ports_scanned,
            "open_ports_count": scan_result.open_ports_count,
            "http_services_count": scan_result.http_services_count,
            "admin_directories_count": len(scan_result.admin_directories)
        },
        "open_ports": [
            {
                "port": port.port,
                "protocol": port.protocol.value,
                "state": port.state,
                "service": port.service,
                "version": port.version,
                "banner": port.banner,
                "confidence": port.confidence
            }
            for port in scan_result.open_ports
        ],
        "http_services": [
            {
                "url": http.url,
                "status_code": http.status_code,
                "title": http.title,
                "server": http.server,
                "technologies": http.technologies,
                "is_https": http.is_https,
                "response_time": http.response_time
            }
            for http in scan_result.http_services
        ],
        "admin_directories": [
            {
                "path": dir_info.path,
                "status_code": dir_info.status_code,
                "title": dir_info.title,
                "is_admin": dir_info.is_admin,
                "content_type": dir_info.content_type,
                "response_time": dir_info.response_time
            }
            for dir_info in scan_result.admin_directories
        ]
    }
    
    if scan_result.error_message:
        result_data["error"] = scan_result.error_message
    
    return [TextContent(type="text", text=json.dumps(result_data, indent=2, ensure_ascii=False))]

async def execute_scan(scan_result: ScanResult, scan_layers: List[str], config: ScanConfig) -> None:
    """执行单个扫描"""
    try:
        # 更新扫描器配置
        scanner.config = config
        http_detector.config = config
        web_prober.config = config
        
        # 第一层：端口扫描
        if "port_scan" in scan_layers:
            logger.info(f"🔍 执行常用端口扫描: {scan_result.target.ip}")
            port_infos = await scanner.scan_target(scan_result.target)
            
            for port_info in port_infos:
                scan_result.add_port(port_info)
            
            scan_result.total_ports_scanned = len(port_infos)
            logger.info(f"📊 常用端口扫描完成: {scan_result.target.ip}，发现 {len(port_infos)} 个开放端口")
            
            # 🧠 智能扫描决策：根据流程图实现全端口扫描逻辑
            if not scan_result.target.ports and config.smart_scan_enabled:  # 只有未指定端口时才进行智能决策
                logger.info(f"🧠 智能扫描决策: 发现 {len(port_infos)} 个端口，阈值 {config.smart_scan_threshold}")
                
                if len(port_infos) < config.smart_scan_threshold:
                    logger.info(f"🔥 触发全端口扫描: 端口数({len(port_infos)}) < 阈值({config.smart_scan_threshold})")
                    logger.info(f"🚀 开始全端口深度扫描 (1-65535) - 可能有隐藏服务")
                    
                    # 创建全端口扫描目标
                    full_target = ScanTarget(
                        ip=scan_result.target.ip,
                        ports=None  # 使用None让RustScan使用全端口范围
                    )
                    
                    # 临时修改配置为全端口扫描
                    original_ports = scanner.config.rustscan_ports
                    scanner.config.rustscan_ports = "1-65535"
                    
                    try:
                        # 执行全端口扫描
                        full_port_infos = await scanner.scan_target(full_target)
                        
                        # 替换为全端口扫描结果
                        scan_result.open_ports.clear()
                        for port_info in full_port_infos:
                            scan_result.add_port(port_info)
                        
                        scan_result.total_ports_scanned = len(full_port_infos)
                        logger.info(f"🎉 全端口扫描完成: {scan_result.target.ip}，最终发现 {len(full_port_infos)} 个开放端口")
                        
                    finally:
                        # 恢复原始配置
                        scanner.config.rustscan_ports = original_ports
                        
                else:
                    logger.info(f"⏭️ 跳过全端口扫描: 端口数({len(port_infos)}) >= 阈值({config.smart_scan_threshold}) - 已获得足够信息")
            else:
                if scan_result.target.ports:
                    logger.info(f"🎯 指定端口扫描: 跳过智能决策")
                else:
                    logger.info(f"⚙️ 智能扫描已禁用")
        
        # 第二层：HTTP服务检测
        if "http_detection" in scan_layers and scan_result.open_ports:
            logger.info(f"执行HTTP服务检测: {scan_result.target.ip}")
            http_services = await http_detector.detect_http_services(
                scan_result.target.ip, 
                scan_result.open_ports
            )
            
            for http_service in http_services:
                scan_result.add_http_service(http_service)
            
            logger.info(f"HTTP服务检测完成: {scan_result.target.ip}，发现 {len(http_services)} 个HTTP服务")
        
        # 第三层：Web深度探测
        if "web_probe" in scan_layers and scan_result.http_services:
            logger.info(f"执行Web深度探测: {scan_result.target.ip}")
            admin_directories = await web_prober.probe_web_services(scan_result.http_services)
            
            for dir_info in admin_directories:
                scan_result.add_admin_directory(dir_info)
            
            logger.info(f"Web深度探测完成: {scan_result.target.ip}，发现 {len(admin_directories)} 个目录")
        
        # 标记完成
        scan_result.mark_completed()
        logger.info(f"扫描完成: {scan_result.target.ip} (耗时: {scan_result.scan_duration:.2f}秒)")
        
    except Exception as e:
        logger.error(f"扫描失败: {scan_result.target.ip}, {e}")
        scan_result.mark_failed(str(e))

async def execute_batch_scan(scan_results: List[ScanResult], scan_layers: List[str], max_concurrent: int) -> None:
    """执行批量扫描"""
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def scan_with_semaphore(scan_result: ScanResult) -> None:
        async with semaphore:
            scan_result.status = ScanStatus.RUNNING
            await execute_scan(scan_result, scan_layers, ScanConfig())
    
    # 并发执行所有扫描
    tasks = [scan_with_semaphore(result) for result in scan_results]
    await asyncio.gather(*tasks, return_exceptions=True)
    
    logger.info(f"批量扫描完成，共 {len(scan_results)} 个目标")

async def main():
    """主函数"""
    logger.info("启动MCP端口扫描服务器")
    
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream, 
            write_stream, 
            server.create_initialization_options()
        )

if __name__ == "__main__":
    asyncio.run(main()) 