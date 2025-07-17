#!/usr/bin/env python3
"""
Cursor SSE适配器
专门为Cursor编辑器优化的SSE实时进度接口
"""

import asyncio
import json
import uuid
from typing import Dict, List, Any, Optional, AsyncGenerator
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .service import ScanService
from .models import ScanConfig, ScanTarget, ScanResult, ScanStatus
from .logger_config import logger


class CursorScanRequest(BaseModel):
    """Cursor扫描请求模型"""
    ip: str
    ports: Optional[List[int]] = None
    scan_layers: List[str] = ["port_scan", "http_detection", "web_probe"]
    real_time: bool = True
    config: Optional[Dict[str, Any]] = None


class CursorSSEAdapter:
    """Cursor SSE适配器"""
    
    def __init__(self):
        self.app = FastAPI(
            title="MCP Port Scanner for Cursor",
            description="优化的Cursor SSE接口",
            version="1.0.0"
        )
        
        # 配置CORS支持Cursor
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # 扫描状态管理
        self.active_scans: Dict[str, ScanResult] = {}
        self.scan_services: Dict[str, ScanService] = {}
        
        logger.info("CursorSSEAdapter: 初始化完成，启用CORS支持")
        self._setup_routes()
    
    def _setup_routes(self):
        """设置路由"""
        
        @self.app.get("/")
        async def root():
            return {
                "service": "MCP Port Scanner - Cursor SSE",
                "version": "1.0.0",
                "description": "为Cursor编辑器优化的实时端口扫描接口",
                "endpoints": {
                    "scan": "POST /cursor/scan - 启动实时扫描",
                    "stream": "GET /cursor/scan/{scan_id}/stream - SSE进度流",
                    "status": "GET /cursor/scan/{scan_id} - 扫描状态"
                }
            }
        
        @self.app.post("/cursor/scan")
        async def cursor_scan(request: CursorScanRequest):
            """Cursor优化的扫描接口"""
            scan_id = str(uuid.uuid4())
            logger.info(f"CursorSSE: 收到扫描请求 - IP={request.ip}, ports={request.ports}, scan_id={scan_id}")
            
            # 创建配置
            config_dict = request.config or {}
            config = ScanConfig(**config_dict)
            
            # 创建服务和目标
            service = ScanService(config)
            target = ScanTarget(ip=request.ip, ports=request.ports)
            
            # 创建扫描结果
            scan_result = ScanResult(
                target=target,
                scan_id=scan_id,
                status=ScanStatus.PENDING
            )
            
            self.active_scans[scan_id] = scan_result
            self.scan_services[scan_id] = service
            
            # 启动后台扫描
            logger.debug(f"CursorSSE: 启动后台扫描任务 - scan_id={scan_id}")
            asyncio.create_task(self._execute_scan(scan_id, service, request))
            
            return {
                "scan_id": scan_id,
                "status": "started",
                "target": request.ip,
                "stream_url": f"/cursor/scan/{scan_id}/stream",
                "cursor_compatible": True,
                "real_time": request.real_time
            }
        
        @self.app.get("/cursor/scan/{scan_id}/stream")
        async def cursor_stream(scan_id: str):
            """Cursor优化的SSE流"""
            if scan_id not in self.active_scans:
                raise HTTPException(status_code=404, detail="扫描不存在")
            
            return StreamingResponse(
                self._generate_cursor_events(scan_id),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "Access-Control-Allow-Origin": "*",
                    "X-Accel-Buffering": "no",  # 禁用nginx缓冲
                }
            )
        
        @self.app.get("/cursor/scan/{scan_id}")
        async def cursor_status(scan_id: str):
            """获取扫描状态"""
            if scan_id not in self.active_scans:
                raise HTTPException(status_code=404, detail="扫描不存在")
            
            scan_result = self.active_scans[scan_id]
            return self._format_cursor_status(scan_result)
    
    async def _execute_scan(self, scan_id: str, service: ScanService, request: CursorScanRequest):
        """执行扫描任务"""
        scan_result = self.active_scans[scan_id]
        logger.info(f"CursorSSE: 开始执行扫描 - scan_id={scan_id}, target={request.ip}")
        
        try:
            scan_result.status = ScanStatus.RUNNING
            
            # 执行扫描
            result = await service.scan_async(
                request.ip, 
                request.ports, 
                request.scan_layers
            )
            
            # 更新结果
            scan_result.open_ports = result.open_ports
            scan_result.http_services = result.http_services
            scan_result.admin_directories = result.admin_directories
            scan_result.scan_duration = result.scan_duration
            scan_result.end_time = result.end_time
            scan_result.status = ScanStatus.COMPLETED
            
            logger.info(f"CursorSSE: 扫描完成 - scan_id={scan_id}, 发现 {len(result.open_ports)} 个端口")
            
        except Exception as e:
            logger.error(f"CursorSSE: 扫描失败 - scan_id={scan_id}, error={e}", exc_info=True)
            scan_result.status = ScanStatus.FAILED
            scan_result.error_message = str(e)
            scan_result.end_time = datetime.now()
        
        finally:
            # 清理
            if scan_id in self.scan_services:
                del self.scan_services[scan_id]
                logger.debug(f"CursorSSE: 清理扫描服务 - scan_id={scan_id}")
    
    async def _generate_cursor_events(self, scan_id: str) -> AsyncGenerator[str, None]:
        """生成Cursor优化的SSE事件"""
        scan_result = self.active_scans[scan_id]
        last_status = None
        last_ports_count = 0
        last_http_count = 0
        last_admin_count = 0
        
        logger.debug(f"CursorSSE: 开始生成SSE事件流 - scan_id={scan_id}")
        
        # 发送开始事件
        yield f"data: {json.dumps(self._cursor_event('start', {'scan_id': scan_id, 'target': scan_result.target.ip}))}\n\n"
        
        while True:
            if scan_id not in self.active_scans:
                break
            
            current = self.active_scans[scan_id]
            current_status = current.status
            
            # 状态变化
            if current_status != last_status:
                yield f"data: {json.dumps(self._cursor_event('status', {'status': current_status.value, 'scan_id': scan_id}))}\n\n"
                last_status = current_status
            
            # 进度变化
            ports_count = len(current.open_ports)
            http_count = len(current.http_services)
            admin_count = len([d for d in current.admin_directories if d.is_admin])
            
            if (ports_count != last_ports_count or 
                http_count != last_http_count or 
                admin_count != last_admin_count):
                
                yield f"data: {json.dumps(self._cursor_event('progress', {
                    'scan_id': scan_id,
                    'open_ports': ports_count,
                    'http_services': http_count,
                    'admin_interfaces': admin_count,
                    'new_ports': ports_count - last_ports_count,
                    'new_http': http_count - last_http_count,
                    'new_admin': admin_count - last_admin_count
                }))}\n\n"
                
                last_ports_count = ports_count
                last_http_count = http_count
                last_admin_count = admin_count
            
            # 完成处理
            if current_status in [ScanStatus.COMPLETED, ScanStatus.FAILED]:
                if current_status == ScanStatus.COMPLETED:
                    yield f"data: {json.dumps(self._cursor_event('complete', self._format_cursor_result(current)))}\n\n"
                else:
                    yield f"data: {json.dumps(self._cursor_event('error', {'error': current.error_message, 'scan_id': scan_id}))}\n\n"
                break
            
            await asyncio.sleep(0.5)  # Cursor优化：更频繁的更新
    
    def _cursor_event(self, event_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """格式化Cursor事件"""
        return {
            "type": event_type,
            "timestamp": datetime.now().isoformat(),
            "data": data
        }
    
    def _format_cursor_status(self, scan_result: ScanResult) -> Dict[str, Any]:
        """格式化Cursor状态"""
        return {
            "scan_id": scan_result.scan_id,
            "target": scan_result.target.ip,
            "status": scan_result.status.value,
            "progress": {
                "open_ports": len(scan_result.open_ports),
                "http_services": len(scan_result.http_services),
                "admin_interfaces": len([d for d in scan_result.admin_directories if d.is_admin])
            },
            "timing": {
                "start_time": scan_result.start_time.isoformat(),
                "duration": scan_result.scan_duration,
                "end_time": scan_result.end_time.isoformat() if scan_result.end_time else None
            },
            "cursor_optimized": True
        }
    
    def _format_cursor_result(self, scan_result: ScanResult) -> Dict[str, Any]:
        """格式化Cursor完整结果"""
        return {
            "scan_id": scan_result.scan_id,
            "target": scan_result.target.ip,
            "summary": {
                "total_ports": len(scan_result.open_ports),
                "http_services": len(scan_result.http_services),
                "admin_interfaces": len([d for d in scan_result.admin_directories if d.is_admin]),
                "scan_duration": scan_result.scan_duration
            },
            "open_ports": [
                {
                    "port": p.port,
                    "service": p.service,
                    "version": p.version,
                    "banner": p.banner[:100] if p.banner else None  # 限制长度
                }
                for p in scan_result.open_ports[:20]  # 限制数量
            ],
            "http_services": [
                {
                    "url": h.url,
                    "status": h.status_code,
                    "title": h.title,
                    "server": h.server
                }
                for h in scan_result.http_services[:10]
            ],
            "admin_interfaces": [
                {
                    "path": d.path,
                    "title": d.title,
                    "status": d.status_code
                }
                for d in scan_result.admin_directories if d.is_admin
            ][:5],
            "cursor_optimized": True
        }


# 创建应用实例
cursor_adapter = CursorSSEAdapter()
app = cursor_adapter.app


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8080) 