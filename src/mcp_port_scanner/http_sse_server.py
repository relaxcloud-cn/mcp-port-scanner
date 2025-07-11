#!/usr/bin/env python3
"""
HTTP/SSE桥接服务器
为现有MCP端口扫描器提供HTTP和SSE接口，不修改原有架构
"""

import asyncio
import json
import uuid
import time
from typing import Dict, List, Any, Optional, AsyncGenerator
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
from loguru import logger

# 导入现有服务层（不修改现有架构）
from .service import ScanService
from .models import ScanConfig, ScanTarget, ScanResult, ScanStatus


class ScanRequest(BaseModel):
    """HTTP扫描请求模型"""
    target: str
    ports: Optional[List[int]] = None
    scan_layers: List[str] = ["port_scan", "http_detection", "web_probe"]
    config: Optional[Dict[str, Any]] = None


class BatchScanRequest(BaseModel):
    """批量扫描请求模型"""
    targets: List[str]
    scan_layers: List[str] = ["port_scan", "http_detection", "web_probe"]
    max_concurrent: int = 5
    config: Optional[Dict[str, Any]] = None


# 全局状态管理（复用现有设计）
active_scans: Dict[str, ScanResult] = {}
scan_services: Dict[str, ScanService] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    logger.info("🚀 HTTP/SSE桥接服务器启动")
    yield
    logger.info("🛑 HTTP/SSE桥接服务器关闭")


# 创建FastAPI应用
app = FastAPI(
    title="MCP Port Scanner HTTP/SSE API",
    description="HTTP和SSE接口桥接现有MCP端口扫描服务",
    version="1.0.0",
    lifespan=lifespan
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """API根路径"""
    return {
        "service": "MCP Port Scanner HTTP/SSE Bridge",
        "version": "1.0.0",
        "description": "桥接现有MCP stdio服务器的HTTP/SSE接口",
        "endpoints": {
            "scan": "POST /scan - 单目标扫描",
            "batch_scan": "POST /batch_scan - 批量扫描",
            "scan_stream": "GET /scan/{scan_id}/stream - SSE实时进度",
            "scan_status": "GET /scan/{scan_id}/status - 扫描状态",
            "scan_result": "GET /scan/{scan_id}/result - 扫描结果",
            "active_scans": "GET /scans - 活跃扫描列表"
        },
        "features": [
            "保持现有MCP架构不变",
            "HTTP API接口",
            "SSE实时进度推送",
            "批量扫描支持",
            "智能扫描策略"
        ]
    }


@app.post("/scan")
async def start_scan(request: ScanRequest, background_tasks: BackgroundTasks):
    """启动单目标扫描"""
    scan_id = str(uuid.uuid4())
    
    # 创建扫描配置
    config_dict = request.config or {}
    config = ScanConfig(**config_dict)
    
    # 创建扫描服务实例
    service = ScanService(config)
    scan_services[scan_id] = service
    
    # 创建扫描目标
    target = ScanTarget(ip=request.target, ports=request.ports)
    
    # 创建扫描结果对象
    scan_result = ScanResult(
        target=target,
        scan_id=scan_id,
        status=ScanStatus.PENDING
    )
    active_scans[scan_id] = scan_result
    
    # 启动后台扫描任务
    background_tasks.add_task(
        execute_scan_task, 
        scan_id, 
        service, 
        request.target, 
        request.ports, 
        request.scan_layers
    )
    
    logger.info(f"启动扫描任务: {scan_id} -> {request.target}")
    
    return {
        "scan_id": scan_id,
        "status": "started",
        "target": request.target,
        "scan_layers": request.scan_layers,
        "stream_url": f"/scan/{scan_id}/stream",
        "status_url": f"/scan/{scan_id}/status",
        "result_url": f"/scan/{scan_id}/result"
    }


@app.post("/batch_scan")
async def start_batch_scan(request: BatchScanRequest, background_tasks: BackgroundTasks):
    """启动批量扫描"""
    batch_id = str(uuid.uuid4())
    scan_ids = []
    
    # 为每个目标创建扫描任务
    for target in request.targets:
        scan_id = str(uuid.uuid4())
        scan_ids.append(scan_id)
        
        # 创建配置和服务
        config_dict = request.config or {}
        config = ScanConfig(**config_dict)
        service = ScanService(config)
        scan_services[scan_id] = service
        
        # 创建扫描结果
        target_obj = ScanTarget(ip=target)
        scan_result = ScanResult(
            target=target_obj,
            scan_id=scan_id,
            status=ScanStatus.PENDING
        )
        active_scans[scan_id] = scan_result
        
        # 启动后台任务
        background_tasks.add_task(
            execute_scan_task,
            scan_id,
            service,
            target,
            None,
            request.scan_layers
        )
    
    logger.info(f"启动批量扫描: {batch_id}, {len(request.targets)}个目标")
    
    return {
        "batch_id": batch_id,
        "scan_ids": scan_ids,
        "targets_count": len(request.targets),
        "status": "started",
        "max_concurrent": request.max_concurrent
    }


@app.get("/scan/{scan_id}/stream")
async def scan_stream(scan_id: str):
    """SSE实时进度流"""
    if scan_id not in active_scans:
        raise HTTPException(status_code=404, detail="扫描任务不存在")
    
    async def event_generator() -> AsyncGenerator[str, None]:
        """SSE事件生成器"""
        scan_result = active_scans[scan_id]
        last_status = None
        
        # 发送初始状态
        yield f"data: {json.dumps({'type': 'start', 'scan_id': scan_id, 'target': scan_result.target.ip})}\n\n"
        
        # 持续监控扫描状态
        while True:
            if scan_id not in active_scans:
                break
                
            current_result = active_scans[scan_id]
            current_status = current_result.status
            
            # 状态变化时推送更新
            if current_status != last_status:
                event_data = {
                    "type": "status_update",
                    "scan_id": scan_id,
                    "status": current_status.value,
                    "target": current_result.target.ip,
                    "timestamp": datetime.now().isoformat()
                }
                
                # 添加进度信息
                if current_status == ScanStatus.RUNNING:
                    event_data.update({
                        "open_ports_count": len(current_result.open_ports),
                        "http_services_count": len(current_result.http_services),
                        "admin_directories_count": len(current_result.admin_directories)
                    })
                
                yield f"data: {json.dumps(event_data)}\n\n"
                last_status = current_status
            
            # 扫描完成时发送最终结果
            if current_status in [ScanStatus.COMPLETED, ScanStatus.FAILED]:
                final_data = {
                    "type": "complete",
                    "scan_id": scan_id,
                    "status": current_status.value,
                    "duration": current_result.scan_duration,
                    "summary": {
                        "open_ports": len(current_result.open_ports),
                        "http_services": len(current_result.http_services),
                        "admin_directories": len(current_result.admin_directories)
                    }
                }
                yield f"data: {json.dumps(final_data)}\n\n"
                break
            
            await asyncio.sleep(1)  # 1秒检查一次
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
        }
    )


@app.get("/scan/{scan_id}/status")
async def get_scan_status(scan_id: str):
    """获取扫描状态"""
    if scan_id not in active_scans:
        raise HTTPException(status_code=404, detail="扫描任务不存在")
    
    scan_result = active_scans[scan_id]
    
    return {
        "scan_id": scan_id,
        "status": scan_result.status.value,
        "target": scan_result.target.ip,
        "start_time": scan_result.start_time.isoformat(),
        "end_time": scan_result.end_time.isoformat() if scan_result.end_time else None,
        "duration": scan_result.scan_duration,
        "progress": {
            "open_ports_count": len(scan_result.open_ports),
            "http_services_count": len(scan_result.http_services),
            "admin_directories_count": len(scan_result.admin_directories)
        },
        "error_message": scan_result.error_message
    }


@app.get("/scan/{scan_id}/result")
async def get_scan_result(scan_id: str):
    """获取完整扫描结果"""
    if scan_id not in active_scans:
        raise HTTPException(status_code=404, detail="扫描任务不存在")
    
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
            "open_ports_count": len(scan_result.open_ports),
            "http_services_count": len(scan_result.http_services),
            "admin_directories_count": len(scan_result.admin_directories)
        },
        "open_ports": [
            {
                "port": port.port,
                "protocol": port.protocol.value,
                "state": port.state,
                "service": port.service,
                "version": port.version,
                "banner": port.banner[:200] if port.banner else None,  # 限制banner长度
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
    
    return result_data


@app.get("/scans")
async def list_active_scans():
    """列出所有活跃扫描"""
    scans_list = []
    
    for scan_id, scan_result in active_scans.items():
        scan_info = {
            "scan_id": scan_id,
            "status": scan_result.status.value,
            "target": scan_result.target.ip,
            "start_time": scan_result.start_time.isoformat(),
            "duration": scan_result.scan_duration,
            "progress": {
                "open_ports": len(scan_result.open_ports),
                "http_services": len(scan_result.http_services),
                "admin_directories": len(scan_result.admin_directories)
            }
        }
        scans_list.append(scan_info)
    
    return {
        "active_scans_count": len(scans_list),
        "scans": scans_list
    }


async def execute_scan_task(scan_id: str, service: ScanService, target: str, 
                           ports: Optional[List[int]], scan_layers: List[str]):
    """执行扫描任务（后台任务）"""
    scan_result = active_scans[scan_id]
    
    try:
        # 更新状态为运行中
        scan_result.status = ScanStatus.RUNNING
        logger.info(f"开始执行扫描: {scan_id} -> {target}")
        
        # 执行扫描（使用现有服务层）
        result = await service.scan_async(target, ports, scan_layers)
        
        # 更新扫描结果
        scan_result.open_ports = result.open_ports
        scan_result.http_services = result.http_services
        scan_result.admin_directories = result.admin_directories
        scan_result.scan_duration = result.scan_duration
        scan_result.end_time = result.end_time
        scan_result.status = ScanStatus.COMPLETED
        
        logger.info(f"扫描完成: {scan_id} -> {target} ({result.scan_duration:.2f}s)")
        
    except Exception as e:
        logger.error(f"扫描失败: {scan_id} -> {target}, {e}")
        scan_result.status = ScanStatus.FAILED
        scan_result.error_message = str(e)
        scan_result.end_time = datetime.now()
    
    finally:
        # 清理服务实例
        if scan_id in scan_services:
            del scan_services[scan_id]


def start_server(host: str = "127.0.0.1", port: int = 8080, 
                workers: int = 1, log_level: str = "info"):
    """启动HTTP/SSE服务器"""
    logger.info(f"🌐 启动HTTP/SSE桥接服务器: http://{host}:{port}")
    
    # 配置日志
    logger.add(
        "logs/http_sse_server_{time}.log",
        level=log_level.upper(),
        rotation="1 day",
        retention="7 days"
    )
    
    # 启动服务器
    uvicorn.run(
        "mcp_port_scanner.http_sse_server:app",
        host=host,
        port=port,
        workers=workers,
        log_level=log_level,
        access_log=True,
        reload=False
    )


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="MCP端口扫描器 HTTP/SSE桥接服务器")
    parser.add_argument("--host", default="127.0.0.1", help="监听地址")
    parser.add_argument("--port", type=int, default=8080, help="监听端口")
    parser.add_argument("--workers", type=int, default=1, help="工作进程数")
    parser.add_argument("--log-level", default="info", help="日志级别")
    
    args = parser.parse_args()
    
    start_server(
        host=args.host,
        port=args.port,
        workers=args.workers,
        log_level=args.log_level
    ) 