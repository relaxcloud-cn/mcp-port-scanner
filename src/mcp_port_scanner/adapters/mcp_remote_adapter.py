"""
MCP远程适配器
处理基于HTTP + SSE的远程MCP协议请求和响应
"""

import json
import asyncio
from typing import Any, Dict, List, Optional, AsyncGenerator
from datetime import datetime
import uuid

from . import StreamingAdapter
from ..service import ScanService, CallbackType, ScanProgress
from ..models import ScanResult, ScanConfig, ScanTarget


class MCPRemoteAdapter(StreamingAdapter):
    """MCP远程适配器（HTTP + SSE）"""
    
    def __init__(self, service: Optional[ScanService] = None):
        self.service = service or ScanService()
        # 存储SSE连接的扫描任务
        self.sse_scans: Dict[str, asyncio.Task] = {}
    
    async def handle_request(self, request_data: Dict[str, Any]) -> Any:
        """
        处理HTTP API请求（非流式）
        
        Args:
            request_data: HTTP请求数据
                - tool_name: 工具名称
                - arguments: 工具参数
                - stream: 是否流式响应
                
        Returns:
            扫描结果或扫描ID
        """
        tool_name = request_data.get("tool_name")
        arguments = request_data.get("arguments", {})
        is_stream = request_data.get("stream", False)
        
        if is_stream:
            # 流式响应，返回扫描ID
            return await self._start_streaming_scan(tool_name, arguments)
        else:
            # 同步响应
            if tool_name == "scan_target":
                return await self._handle_scan_target(arguments)
            elif tool_name == "batch_scan":
                return await self._handle_batch_scan(arguments)
            elif tool_name == "get_scan_status":
                return await self._handle_get_scan_status(arguments)
            elif tool_name == "get_scan_result":
                return await self._handle_get_scan_result(arguments)
            elif tool_name == "list_active_scans":
                return await self._handle_list_active_scans(arguments)
            else:
                raise ValueError(f"不支持的工具: {tool_name}")
    
    async def handle_streaming_request(self, request_data: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
        """
        处理SSE流式请求
        
        Args:
            request_data: 流式请求数据
                - scan_id: 扫描ID（可选，用于监听已存在的扫描）
                - tool_name: 工具名称（用于新建扫描）
                - arguments: 工具参数
                
        Yields:
            Dict[str, Any]: SSE事件数据
        """
        scan_id = request_data.get("scan_id")
        
        if scan_id:
            # 监听已存在的扫描
            async for event in self._stream_existing_scan(scan_id):
                yield event
        else:
            # 新建扫描并流式返回结果
            tool_name = request_data.get("tool_name")
            arguments = request_data.get("arguments", {})
            
            async for event in self._stream_new_scan(tool_name, arguments):
                yield event
    
    async def _start_streaming_scan(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """启动流式扫描，返回扫描ID"""
        scan_id = str(uuid.uuid4())
        
        # 创建扫描任务但不等待完成
        if tool_name == "scan_target":
            ip = arguments["ip"]
            ports = arguments.get("ports")
            scan_layers = arguments.get("scan_layers", ["port_scan", "http_detection", "web_probe"])
            
            scan_task = asyncio.create_task(
                self.service.scan_async(ip, ports, scan_layers, scan_id)
            )
            self.sse_scans[scan_id] = scan_task
            
            return {
                "scan_id": scan_id,
                "status": "started",
                "target": ip,
                "message": "扫描已启动，请使用SSE监听进度"
            }
        else:
            raise ValueError(f"流式模式不支持工具: {tool_name}")
    
    async def _stream_existing_scan(self, scan_id: str) -> AsyncGenerator[Dict[str, Any], None]:
        """流式监听已存在的扫描"""
        # 首先发送开始事件
        yield {
            "event": "scan_start",
            "data": {
                "scan_id": scan_id,
                "timestamp": datetime.now().isoformat()
            }
        }
        
        # 监听扫描进度
        last_status = None
        while True:
            scan_result = self.service.get_scan_status(scan_id)
            
            if scan_result is None:
                yield {
                    "event": "error",
                    "data": {
                        "scan_id": scan_id,
                        "error": "扫描不存在",
                        "timestamp": datetime.now().isoformat()
                    }
                }
                break
            
            # 检查状态变化
            current_status = scan_result.status.value
            if current_status != last_status:
                yield {
                    "event": "status_change",
                    "data": {
                        "scan_id": scan_id,
                        "status": current_status,
                        "timestamp": datetime.now().isoformat()
                    }
                }
                last_status = current_status
            
            # 如果扫描完成，发送最终结果
            if current_status in ["completed", "failed"]:
                if current_status == "completed":
                    yield {
                        "event": "scan_complete",
                        "data": self._format_sse_result(scan_result)
                    }
                else:
                    yield {
                        "event": "scan_failed",
                        "data": {
                            "scan_id": scan_id,
                            "error": scan_result.error_message,
                            "timestamp": datetime.now().isoformat()
                        }
                    }
                
                # 清理扫描任务
                if scan_id in self.sse_scans:
                    del self.sse_scans[scan_id]
                break
            
            # 等待1秒后继续检查
            await asyncio.sleep(1)
    
    async def _stream_new_scan(self, tool_name: str, arguments: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
        """创建新扫描并流式返回结果"""
        scan_id = str(uuid.uuid4())
        
        # 发送开始事件
        yield {
            "event": "scan_start",
            "data": {
                "scan_id": scan_id,
                "tool_name": tool_name,
                "arguments": arguments,
                "timestamp": datetime.now().isoformat()
            }
        }
        
        try:
            if tool_name == "scan_target":
                async for event in self._stream_scan_target(scan_id, arguments):
                    yield event
            elif tool_name == "batch_scan":
                async for event in self._stream_batch_scan(scan_id, arguments):
                    yield event
            else:
                yield {
                    "event": "error",
                    "data": {
                        "scan_id": scan_id,
                        "error": f"流式模式不支持工具: {tool_name}",
                        "timestamp": datetime.now().isoformat()
                    }
                }
        except Exception as e:
            yield {
                "event": "error",
                "data": {
                    "scan_id": scan_id,
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                }
            }
    
    async def _stream_scan_target(self, scan_id: str, arguments: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
        """流式执行单目标扫描"""
        ip = arguments["ip"]
        ports = arguments.get("ports")
        scan_layers = arguments.get("scan_layers", ["port_scan", "http_detection", "web_probe"])
        
        # 注册进度回调
        progress_queue = asyncio.Queue()
        
        async def progress_callback(callback_type: CallbackType, data: Any):
            await progress_queue.put({
                "callback_type": callback_type,
                "data": data
            })
        
        # 注册所有回调
        callback_types = [CallbackType.ON_START, CallbackType.ON_PROGRESS, 
                         CallbackType.ON_LAYER_COMPLETE, CallbackType.ON_COMPLETE, CallbackType.ON_ERROR]
        
        for callback_type in callback_types:
            self.service.register_callback(scan_id, callback_type, progress_callback)
        
        # 启动扫描任务
        scan_task = asyncio.create_task(
            self.service.scan_async(ip, ports, scan_layers, scan_id)
        )
        
        # 监听进度并发送SSE事件
        result = None
        while True:
            try:
                # 等待进度更新或任务完成
                done, pending = await asyncio.wait(
                    [progress_queue.get(), scan_task],
                    return_when=asyncio.FIRST_COMPLETED,
                    timeout=1.0
                )
                
                if scan_task in done:
                    # 扫描完成
                    try:
                        result = scan_task.result()
                        yield {
                            "event": "scan_complete",
                            "data": self._format_sse_result(result)
                        }
                    except Exception as e:
                        yield {
                            "event": "scan_failed",
                            "data": {
                                "scan_id": scan_id,
                                "error": str(e),
                                "timestamp": datetime.now().isoformat()
                            }
                        }
                    break
                
                # 处理进度回调
                for task in done:
                    if task != scan_task:
                        progress_data = task.result()
                        callback_type = progress_data["callback_type"]
                        callback_data = progress_data["data"]
                        
                        if callback_type == CallbackType.ON_LAYER_COMPLETE:
                            layer_name, progress_percent = callback_data
                            yield {
                                "event": "layer_complete",
                                "data": {
                                    "scan_id": scan_id,
                                    "layer": layer_name,
                                    "progress": progress_percent,
                                    "timestamp": datetime.now().isoformat()
                                }
                            }
                        elif callback_type == CallbackType.ON_PROGRESS:
                            yield {
                                "event": "progress",
                                "data": {
                                    "scan_id": scan_id,
                                    **callback_data,
                                    "timestamp": datetime.now().isoformat()
                                }
                            }
                
            except asyncio.TimeoutError:
                # 发送心跳
                yield {
                    "event": "heartbeat",
                    "data": {
                        "scan_id": scan_id,
                        "timestamp": datetime.now().isoformat()
                    }
                }
    
    async def _stream_batch_scan(self, scan_id: str, arguments: Dict[str, Any]) -> AsyncGenerator[Dict[str, Any], None]:
        """流式执行批量扫描"""
        targets_data = arguments["targets"]
        scan_layers = arguments.get("scan_layers", ["port_scan", "http_detection", "web_probe"])
        max_concurrent = arguments.get("max_concurrent", 5)
        
        # 转换目标格式
        targets = [ScanTarget(ip=t["ip"], ports=t.get("ports")) for t in targets_data]
        
        # 发送批量扫描开始事件
        yield {
            "event": "batch_start",
            "data": {
                "scan_id": scan_id,
                "total_targets": len(targets),
                "max_concurrent": max_concurrent,
                "timestamp": datetime.now().isoformat()
            }
        }
        
        # 执行批量扫描并监听进度
        completed_count = 0
        results = []
        
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def scan_single_target(target: ScanTarget) -> ScanResult:
            nonlocal completed_count
            async with semaphore:
                result = await self.service.scan_async(target.ip, target.ports, scan_layers)
                completed_count += 1
                
                # 发送单个目标完成事件
                yield {
                    "event": "target_complete",
                    "data": {
                        "scan_id": scan_id,
                        "target": target.ip,
                        "completed": completed_count,
                        "total": len(targets),
                        "progress": (completed_count / len(targets)) * 100,
                        "timestamp": datetime.now().isoformat()
                    }
                }
                
                return result
        
        # 并发执行所有扫描
        tasks = [scan_single_target(target) for target in targets]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理结果
        valid_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                # 处理失败的扫描
                failed_result = ScanResult(
                    target=targets[i],
                    scan_id=str(uuid.uuid4())
                )
                failed_result.mark_failed(str(result))
                valid_results.append(failed_result)
            else:
                valid_results.append(result)
        
        # 发送批量扫描完成事件
        yield {
            "event": "batch_complete",
            "data": self._format_batch_sse_result(scan_id, valid_results)
        }
    
    # 处理非流式请求的方法
    async def _handle_scan_target(self, arguments: Dict[str, Any]) -> ScanResult:
        """处理单目标扫描"""
        ip = arguments["ip"]
        ports = arguments.get("ports")
        scan_layers = arguments.get("scan_layers", ["port_scan", "http_detection", "web_probe"])
        config_dict = arguments.get("config", {})
        
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
        
        # 转换目标格式
        targets = [ScanTarget(ip=t["ip"], ports=t.get("ports")) for t in targets_data]
        
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
    
    async def _handle_list_active_scans(self, arguments: Dict[str, Any]) -> List[ScanResult]:
        """列出活跃扫描"""
        return self.service.list_active_scans()
    
    def format_response(self, result: Any) -> Dict[str, Any]:
        """
        格式化HTTP API响应
        
        Args:
            result: 扫描结果
            
        Returns:
            Dict[str, Any]: HTTP响应数据
        """
        if isinstance(result, list):
            # 批量扫描结果或活跃扫描列表
            return self._format_http_batch_response(result)
        elif isinstance(result, ScanResult):
            # 单个扫描结果
            return self._format_http_single_response(result)
        elif result is None:
            return {"error": "未找到请求的扫描结果"}
        else:
            return {"data": result}
    
    def _format_http_single_response(self, result: ScanResult) -> Dict[str, Any]:
        """格式化HTTP单个扫描结果"""
        return {
            "scan_id": result.scan_id,
            "target": result.target.ip,
            "status": result.status.value,
            "start_time": result.start_time.isoformat() if result.start_time else None,
            "end_time": result.end_time.isoformat() if result.end_time else None,
            "scan_duration": result.scan_duration,
            "summary": {
                "open_ports_count": len(result.open_ports),
                "http_services_count": len(result.http_services),
                "admin_directories_count": len(result.admin_directories),
                "admin_interfaces_count": len([d for d in result.admin_directories if d.is_admin])
            },
            "open_ports": [
                {
                    "port": p.port,
                    "protocol": p.protocol.value,
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
                    "technologies": h.technologies,
                    "is_https": h.is_https,
                    "response_time": h.response_time
                }
                for h in result.http_services
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
                for d in result.admin_directories
            ]
        }
    
    def _format_http_batch_response(self, results: List[ScanResult]) -> Dict[str, Any]:
        """格式化HTTP批量扫描结果"""
        total_hosts = len(results)
        active_hosts = len([r for r in results if r.open_ports])
        total_ports = sum(len(r.open_ports) for r in results)
        total_http = sum(len(r.http_services) for r in results)
        total_admin = sum(len([d for d in r.admin_directories if d.is_admin]) for r in results)
        
        return {
            "summary": {
                "total_hosts": total_hosts,
                "active_hosts": active_hosts,
                "total_ports": total_ports,
                "total_http_services": total_http,
                "total_admin_interfaces": total_admin
            },
            "results": [self._format_http_single_response(result) for result in results]
        }
    
    def _format_sse_result(self, result: ScanResult) -> Dict[str, Any]:
        """格式化SSE扫描结果"""
        return {
            "scan_id": result.scan_id,
            "target": result.target.ip,
            "status": result.status.value,
            "scan_duration": result.scan_duration,
            "summary": {
                "open_ports_count": len(result.open_ports),
                "http_services_count": len(result.http_services),
                "admin_interfaces_count": len([d for d in result.admin_directories if d.is_admin])
            },
            "timestamp": datetime.now().isoformat()
        }
    
    def _format_batch_sse_result(self, scan_id: str, results: List[ScanResult]) -> Dict[str, Any]:
        """格式化SSE批量扫描结果"""
        total_hosts = len(results)
        active_hosts = len([r for r in results if r.open_ports])
        
        return {
            "scan_id": scan_id,
            "summary": {
                "total_hosts": total_hosts,
                "active_hosts": active_hosts,
                "total_ports": sum(len(r.open_ports) for r in results),
                "total_http_services": sum(len(r.http_services) for r in results),
                "total_admin_interfaces": sum(len([d for d in r.admin_directories if d.is_admin]) for r in results)
            },
            "active_hosts": [
                {
                    "ip": r.target.ip,
                    "open_ports": len(r.open_ports),
                    "http_services": len(r.http_services),
                    "admin_interfaces": len([d for d in r.admin_directories if d.is_admin])
                }
                for r in results if r.open_ports
            ],
            "timestamp": datetime.now().isoformat()
        }
    
    def format_progress(self, progress: ScanProgress) -> Dict[str, Any]:
        """
        格式化进度信息
        
        Args:
            progress: 扫描进度
            
        Returns:
            Dict[str, Any]: 格式化的进度数据
        """
        return {
            "event": "progress",
            "data": {
                "scan_id": progress.scan_id,
                "target": progress.target,
                "current_layer": progress.current_layer,
                "progress_percent": progress.progress_percent,
                "message": progress.message,
                "timestamp": progress.timestamp.isoformat()
            }
        }
    
    def format_error(self, error: Exception) -> Dict[str, Any]:
        """
        格式化错误响应
        
        Args:
            error: 异常对象
            
        Returns:
            Dict[str, Any]: 错误响应数据
        """
        return {
            "error": True,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "timestamp": datetime.now().isoformat()
        } 