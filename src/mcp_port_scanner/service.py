"""
统一的端口扫描服务层
提供多种调用模式和接口封装
"""

import asyncio
import uuid
from typing import List, Optional, Dict, Any, Callable, AsyncGenerator, Union
from datetime import datetime
from dataclasses import dataclass
from enum import Enum
import json
from loguru import logger
import time

from .models import (
    ScanTarget, ScanConfig, ScanResult, ScanStatus,
    PortInfo, HTTPInfo, DirectoryInfo
)
from .scanner import PortScanner
from .http_detector import HTTPDetector
from .web_prober import WebProber


class CallbackType(str, Enum):
    """回调类型枚举"""
    ON_START = "on_start"
    ON_PROGRESS = "on_progress"
    ON_LAYER_COMPLETE = "on_layer_complete"
    ON_COMPLETE = "on_complete"
    ON_ERROR = "on_error"


@dataclass
class ScanProgress:
    """扫描进度信息"""
    scan_id: str
    target: str
    current_layer: str
    progress_percent: float
    message: str
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


class ScanService:
    """统一的端口扫描服务"""
    
    def __init__(self, config: Optional[ScanConfig] = None):
        self.config = config or ScanConfig()
        self.port_scanner = PortScanner(self.config)
        self.http_detector = HTTPDetector(self.config)
        self.web_prober = WebProber(self.config)
        
        # 活跃扫描任务管理
        self.active_scans: Dict[str, ScanResult] = {}
        self.scan_callbacks: Dict[str, Dict[CallbackType, List[Callable]]] = {}
        
        # 结果缓存
        self.result_cache: Dict[str, ScanResult] = {}
        
        logger.info("ScanService initialized")
    
    # ==================== 同步调用模式 ====================
    
    def scan_sync(self, 
                  ip: str, 
                  ports: Optional[List[int]] = None,
                  layers: Optional[List[str]] = None) -> ScanResult:
        """
        同步扫描单个目标
        
        Args:
            ip: 目标IP
            ports: 指定端口列表
            layers: 扫描层级
            
        Returns:
            ScanResult: 完整扫描结果
        """
        return asyncio.run(self.scan_async(ip, ports, layers))
    
    def batch_scan_sync(self, 
                       targets: List[Union[str, ScanTarget]],
                       layers: Optional[List[str]] = None,
                       max_concurrent: int = 5) -> List[ScanResult]:
        """
        同步批量扫描
        
        Args:
            targets: 目标列表
            layers: 扫描层级
            max_concurrent: 最大并发数
            
        Returns:
            List[ScanResult]: 扫描结果列表
        """
        return asyncio.run(self.batch_scan_async(targets, layers, max_concurrent))
    
    # ==================== 异步调用模式 ====================
    
    async def scan_async(self, 
                        ip: str, 
                        ports: Optional[List[int]] = None,
                        layers: Optional[List[str]] = None) -> ScanResult:
        """
        异步扫描单个目标
        
        Args:
            ip: 目标IP
            ports: 端口列表（可选）
            layers: 扫描层级（可选）
            
        Returns:
            ScanResult: 扫描结果
        """
        return await self.scan_async_with_progress(ip, ports, layers, None)
    
    async def scan_async_with_progress(self, 
                                     ip: str, 
                                     ports: Optional[List[int]] = None,
                                     layers: Optional[List[str]] = None,
                                     progress_callback: Optional[callable] = None) -> ScanResult:
        """
        异步扫描单个目标（带进度回调）
        
        Args:
            ip: 目标IP
            ports: 端口列表（可选）
            layers: 扫描层级（可选）
            progress_callback: 进度回调函数
            
        Returns:
            ScanResult: 扫描结果
        """
        if layers is None:
            layers = ["port_scan", "http_detection", "web_probe"]
        
        # 创建扫描目标
        target = ScanTarget(ip=ip, ports=ports)
        
        logger.info(f"开始扫描目标: {ip}")
        start_time = time.time()
        
        # 生成扫描ID
        scan_id = str(uuid.uuid4())
        
        result = ScanResult(
            target=target,
            scan_id=scan_id,
            open_ports=[],
            http_services=[],
            admin_directories=[]
        )
        
        try:
            # 1. 端口扫描阶段
            if "port_scan" in layers:
                if progress_callback:
                    await progress_callback("预设端口扫描", "正在扫描常用端口...")
                
                logger.info(f"开始端口扫描: {ip}")
                port_infos = await self.port_scanner.scan_target(target)
                result.open_ports = port_infos
                
                logger.info(f"端口扫描完成，发现 {len(port_infos)} 个开放端口")
                
                # 智能扫描决策
                if not ports:  # 只有在没有指定端口时才进行智能决策
                    if len(port_infos) < self.config.smart_scan_threshold:
                        if progress_callback:
                            await progress_callback("智能决策", f"端口少({len(port_infos)}<{self.config.smart_scan_threshold})，执行全端口扫描...")
                        
                        # 执行全端口扫描
                        logger.info(f"🧠 智能扫描决策: 发现端口数({len(port_infos)}) < 阈值({self.config.smart_scan_threshold})，执行全端口扫描")
                        all_port_infos = await self._execute_full_port_scan(target, progress_callback)
                        result.open_ports = all_port_infos
                        
                        logger.info(f"智能扫描完成，最终发现 {len(all_port_infos)} 个开放端口")
                    else:
                        if progress_callback:
                            await progress_callback("智能决策", f"端口多({len(port_infos)}>={self.config.smart_scan_threshold})，继续Web检测...")
                        logger.info(f"🧠 智能扫描决策: 发现端口数({len(port_infos)}) >= 阈值({self.config.smart_scan_threshold})，跳过全端口扫描")
            
            # 2. HTTP服务检测阶段
            if "http_detection" in layers and result.open_ports:
                if progress_callback:
                    await progress_callback("HTTP服务检测", f"检测 {len(result.open_ports)} 个端口的Web服务...")
                
                logger.info(f"开始HTTP服务检测: {ip}")
                http_services = await self.http_detector.detect_http_services(ip, result.open_ports)
                result.http_services = http_services
                
                logger.info(f"HTTP服务检测完成，发现 {len(http_services)} 个HTTP服务")
            
            # 3. Web探测阶段
            if "web_probe" in layers and result.http_services:
                if progress_callback:
                    await progress_callback("Web探测", f"探测 {len(result.http_services)} 个Web服务...")
                
                logger.info(f"开始Web探测: {ip}")
                admin_directories = await self.web_prober.probe_web_services(result.http_services)
                result.admin_directories = admin_directories
                
                logger.info(f"Web探测完成，发现 {len(admin_directories)} 个目录")
            
            # 计算扫描时间
            result.scan_duration = time.time() - start_time
            
            logger.info(f"扫描完成: {ip}，耗时 {result.scan_duration:.2f}秒")
            
            return result
            
        except Exception as e:
            logger.error(f"扫描失败: {ip} - {e}")
            result.scan_duration = time.time() - start_time
            return result
    
    async def batch_scan_async(self, 
                              targets: List[Union[str, ScanTarget]],
                              layers: Optional[List[str]] = None,
                              max_concurrent: int = 5) -> List[ScanResult]:
        """
        异步批量扫描
        
        Args:
            targets: 目标列表
            layers: 扫描层级
            max_concurrent: 最大并发数
            
        Returns:
            List[ScanResult]: 扫描结果列表
        """
        # 转换目标格式
        scan_targets = []
        for target in targets:
            if isinstance(target, str):
                scan_targets.append(ScanTarget(ip=target))
            else:
                scan_targets.append(target)
        
        # 使用信号量控制并发
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def scan_with_semaphore(target: ScanTarget) -> ScanResult:
            async with semaphore:
                return await self.scan_async(target.ip, target.ports, layers)
        
        # 并发执行所有扫描
        tasks = [scan_with_semaphore(target) for target in scan_targets]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理异常结果
        scan_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                # 创建失败的扫描结果
                failed_result = ScanResult(
                    target=scan_targets[i],
                    scan_id=str(uuid.uuid4())
                )
                failed_result.mark_failed(str(result))
                scan_results.append(failed_result)
            else:
                scan_results.append(result)
        
        return scan_results
    
    # ==================== 流式调用模式 ====================
    
    async def scan_stream(self, 
                         ip: str, 
                         ports: Optional[List[int]] = None,
                         layers: Optional[List[str]] = None) -> AsyncGenerator[ScanProgress, None]:
        """
        流式扫描，实时返回进度
        
        Args:
            ip: 目标IP
            ports: 指定端口列表
            layers: 扫描层级
            
        Yields:
            ScanProgress: 扫描进度信息
        """
        scan_id = str(uuid.uuid4())
        
        # 注册进度回调
        progress_queue = asyncio.Queue()
        
        async def progress_callback(callback_type: CallbackType, data: Any):
            if callback_type == CallbackType.ON_START:
                await progress_queue.put(ScanProgress(
                    scan_id=scan_id,
                    target=ip,
                    current_layer="initializing",
                    progress_percent=0.0,
                    message="开始扫描"
                ))
            elif callback_type == CallbackType.ON_LAYER_COMPLETE:
                layer_name, progress = data
                await progress_queue.put(ScanProgress(
                    scan_id=scan_id,
                    target=ip,
                    current_layer=layer_name,
                    progress_percent=progress,
                    message=f"完成 {layer_name} 层扫描"
                ))
            elif callback_type == CallbackType.ON_COMPLETE:
                await progress_queue.put(ScanProgress(
                    scan_id=scan_id,
                    target=ip,
                    current_layer="completed",
                    progress_percent=100.0,
                    message="扫描完成"
                ))
                await progress_queue.put(None)  # 结束标记
        
        self.register_callback(scan_id, CallbackType.ON_START, progress_callback)
        self.register_callback(scan_id, CallbackType.ON_LAYER_COMPLETE, progress_callback)
        self.register_callback(scan_id, CallbackType.ON_COMPLETE, progress_callback)
        
        # 启动扫描任务
        scan_task = asyncio.create_task(self.scan_async(ip, ports, layers, scan_id))
        
        # 流式返回进度
        while True:
            try:
                progress = await asyncio.wait_for(progress_queue.get(), timeout=1.0)
                if progress is None:  # 结束标记
                    break
                yield progress
            except asyncio.TimeoutError:
                continue
        
        # 等待扫描完成
        await scan_task
    
    # ==================== 回调模式 ====================
    
    def register_callback(self, 
                         scan_id: str, 
                         callback_type: CallbackType, 
                         callback: Callable) -> None:
        """
        注册回调函数
        
        Args:
            scan_id: 扫描ID
            callback_type: 回调类型
            callback: 回调函数
        """
        if scan_id not in self.scan_callbacks:
            self.scan_callbacks[scan_id] = {ct: [] for ct in CallbackType}
        
        self.scan_callbacks[scan_id][callback_type].append(callback)
    
    async def scan_with_callbacks(self, 
                                 ip: str, 
                                 ports: Optional[List[int]] = None,
                                 layers: Optional[List[str]] = None,
                                 callbacks: Optional[Dict[CallbackType, List[Callable]]] = None) -> str:
        """
        使用回调的异步扫描
        
        Args:
            ip: 目标IP
            ports: 指定端口列表
            layers: 扫描层级
            callbacks: 回调函数字典
            
        Returns:
            str: 扫描ID
        """
        scan_id = str(uuid.uuid4())
        
        # 注册回调
        if callbacks:
            for callback_type, callback_list in callbacks.items():
                for callback in callback_list:
                    self.register_callback(scan_id, callback_type, callback)
        
        # 启动异步扫描
        asyncio.create_task(self.scan_async(ip, ports, layers, scan_id))
        
        return scan_id
    
    # ==================== 状态查询接口 ====================
    
    def get_scan_status(self, scan_id: str) -> Optional[ScanResult]:
        """获取扫描状态"""
        # 先查询活跃扫描
        if scan_id in self.active_scans:
            return self.active_scans[scan_id]
        
        # 再查询缓存结果
        if scan_id in self.result_cache:
            return self.result_cache[scan_id]
        
        return None
    
    def list_active_scans(self) -> List[ScanResult]:
        """列出所有活跃扫描"""
        return list(self.active_scans.values())
    
    def get_scan_result(self, scan_id: str) -> Optional[ScanResult]:
        """获取扫描结果"""
        return self.result_cache.get(scan_id)
    
    # ==================== 配置管理 ====================
    
    def update_config(self, config: ScanConfig) -> None:
        """更新配置"""
        self.config = config
        self.port_scanner.config = config
        self.http_detector.config = config
        self.web_prober.config = config
    
    def get_config(self) -> ScanConfig:
        """获取当前配置"""
        return self.config
    
    # ==================== 内部辅助方法 ====================
    
    async def _execute_layered_scan(self, scan_result: ScanResult, layers: List[str]) -> None:
        """执行分层扫描（智能模式）"""
        
        # 如果启用智能扫描且端口列表为空，使用智能扫描逻辑
        if (self.config.smart_scan_enabled and 
            scan_result.target.ports is None and 
            "port_scan" in layers):
            await self._execute_smart_scan(scan_result, layers)
        else:
            # 传统分层扫描模式（向后兼容）
            await self._execute_traditional_scan(scan_result, layers)
    
    async def _execute_smart_scan(self, scan_result: ScanResult, layers: List[str]) -> None:
        """执行智能扫描逻辑"""
        logger.info(f"🧠 启动智能扫描模式，阈值={self.config.smart_scan_threshold}")
        
        # 阶段1：预设端口扫描
        await self._trigger_progress(scan_result.scan_id, "smart_preset_scan", 0.0, 
                                   "🔍 智能扫描 - 预设端口扫描")
        
        # 创建预设扫描目标（RustScan 21-1000 + preset_ports）
        preset_target = ScanTarget(
            ip=scan_result.target.ip,
            ports=None  # None表示使用默认端口范围
        )
        
        # 执行预设端口扫描
        preset_ports = await self.port_scanner.scan_target(preset_target)
        for port_info in preset_ports:
            scan_result.add_port(port_info)
        
        # 预设扫描完成进度
        await self._trigger_progress(scan_result.scan_id, "smart_preset_scan", 30.0, 
                                   f"✅ 预设扫描完成，发现 {len(preset_ports)} 个开放端口")
        
        logger.info(f"💡 预设扫描发现 {len(preset_ports)} 个开放端口")
        
        # 阶段2：智能决策
        open_port_count = len(preset_ports)
        
        await self._trigger_progress(scan_result.scan_id, "smart_decision", 35.0, 
                                   f"🧠 智能决策：端口数量 {open_port_count}，阈值 {self.config.smart_scan_threshold}")
        
        if open_port_count < self.config.smart_scan_threshold:
            # 端口数量少，直接全端口扫描
            await self._trigger_progress(scan_result.scan_id, "smart_decision", 40.0, 
                                       f"🚀 端口较少({open_port_count} < {self.config.smart_scan_threshold})，启动全端口扫描")
            logger.info(f"🚀 开放端口数({open_port_count}) < 阈值({self.config.smart_scan_threshold})，执行全端口扫描")
            await self._execute_full_port_scan(scan_result, exclude_existing=True)
        else:
            # 端口数量足够，检查Web服务
            await self._trigger_progress(scan_result.scan_id, "smart_decision", 40.0, 
                                       f"🌐 端口充足({open_port_count} >= {self.config.smart_scan_threshold})，优先检查Web服务")
            logger.info(f"🌐 开放端口数({open_port_count}) >= 阈值({self.config.smart_scan_threshold})，检查Web服务")
            
            # 检查Web端口的HTTP服务
            has_web_service = await self._check_web_services(scan_result, layers)
            
            if not has_web_service:
                # 没有Web服务，执行全端口扫描
                await self._trigger_progress(scan_result.scan_id, "smart_decision", 70.0, 
                                           "❌ 未发现Web服务，启动剩余端口扫描")
                logger.info("❌ 未发现Web服务，执行剩余端口的全端口扫描")
                await self._execute_full_port_scan(scan_result, exclude_existing=True)
            else:
                await self._trigger_progress(scan_result.scan_id, "smart_decision", 80.0, 
                                           "✅ 发现Web服务，智能策略生效")
                logger.info("✅ 发现Web服务，智能扫描完成")
        
        # 最后执行剩余层级（Web探测等）
        await self._execute_remaining_layers(scan_result, layers)
    
    async def _execute_traditional_scan(self, scan_result: ScanResult, layers: List[str]) -> None:
        """执行传统分层扫描（向后兼容）"""
        total_layers = len(layers)
        
        # 第一层：端口扫描
        if "port_scan" in layers:
            await self._trigger_progress(scan_result.scan_id, "port_scan", 0.0, "开始端口扫描")
            
            port_infos = await self.port_scanner.scan_target(scan_result.target)
            for port_info in port_infos:
                scan_result.add_port(port_info)
            
            progress = (layers.index("port_scan") + 1) / total_layers * 100
            await self._trigger_callback(scan_result.scan_id, CallbackType.ON_LAYER_COMPLETE, 
                                       ("port_scan", progress))
        
        # 第二层：HTTP检测
        if "http_detection" in layers and scan_result.open_ports:
            await self._trigger_progress(scan_result.scan_id, "http_detection", 0.0, "开始HTTP检测")
            
            http_services = await self.http_detector.detect_http_services(
                scan_result.target.ip, scan_result.open_ports
            )
            for http_service in http_services:
                scan_result.add_http_service(http_service)
            
            progress = (layers.index("http_detection") + 1) / total_layers * 100
            await self._trigger_callback(scan_result.scan_id, CallbackType.ON_LAYER_COMPLETE, 
                                       ("http_detection", progress))
        
        # 第三层：Web探测
        if "web_probe" in layers and scan_result.http_services:
            await self._trigger_progress(scan_result.scan_id, "web_probe", 0.0, "开始Web探测")
            
            admin_directories = await self.web_prober.probe_web_services(scan_result.http_services)
            for admin_dir in admin_directories:
                scan_result.add_admin_directory(admin_dir)
            
            progress = (layers.index("web_probe") + 1) / total_layers * 100
            await self._trigger_callback(scan_result.scan_id, CallbackType.ON_LAYER_COMPLETE, 
                                       ("web_probe", progress))
    
    async def _execute_full_port_scan(self, target: ScanTarget, progress_callback: Optional[callable] = None) -> List:
        """执行全端口扫描，返回完整的端口列表"""
        if progress_callback:
            await progress_callback("全端口扫描", "🔥 执行全端口扫描 (1-65535)")
        
        # 创建全端口扫描目标
        full_scan_target = ScanTarget(
            ip=target.ip,
            ports=list(range(1, 65536))
        )
        
        if progress_callback:
            await progress_callback("全端口扫描", "⚡ 全端口扫描进行中...")
        
        # 执行全端口扫描
        full_ports = await self.port_scanner.scan_target(full_scan_target)
        
        if progress_callback:
            await progress_callback("全端口扫描", f"🎉 全端口扫描完成，总共发现 {len(full_ports)} 个开放端口")
        
        logger.info(f"🎉 全端口扫描完成，总共发现 {len(full_ports)} 个开放端口")
        
        return full_ports
    
    async def _check_web_services(self, scan_result: ScanResult, layers: List[str]) -> bool:
        """检查Web端口是否有HTTP服务"""
        if "http_detection" not in layers:
            return False
        
        # 筛选Web端口
        web_ports = []
        for port_info in scan_result.open_ports:
            if port_info.port in self.config.web_ports:
                web_ports.append(port_info)
        
        if not web_ports:
            logger.info("📭 未发现常规Web端口开放")
            return False
        
        logger.info(f"🌐 检测 {len(web_ports)} 个Web端口的HTTP服务")
        
        # 执行HTTP检测
        await self._trigger_progress(scan_result.scan_id, "web_service_check", 0.0, 
                                   "🌐 检测Web端口HTTP服务")
        
        http_services = await self.http_detector.detect_http_services(
            scan_result.target.ip, web_ports
        )
        
        # 添加HTTP服务到结果
        for http_service in http_services:
            scan_result.add_http_service(http_service)
        
        # Web服务检测完成进度
        has_web_service = len(http_services) > 0
        if has_web_service:
            await self._trigger_progress(scan_result.scan_id, "web_service_check", 60.0, 
                                       f"✅ 发现 {len(http_services)} 个HTTP服务")
        else:
            await self._trigger_progress(scan_result.scan_id, "web_service_check", 60.0, 
                                       "❌ 未发现HTTP服务")
        
        logger.info(f"🎯 Web服务检测结果: {len(http_services)} 个HTTP服务")
        
        return has_web_service
    
    async def _execute_remaining_layers(self, scan_result: ScanResult, layers: List[str]) -> None:
        """执行剩余的扫描层级"""
        
        # HTTP检测（如果还没执行过且有端口）
        if ("http_detection" in layers and 
            scan_result.open_ports and 
            not scan_result.http_services):
            
            await self._trigger_progress(scan_result.scan_id, "http_detection", 88.0, 
                                       "🔍 完整HTTP服务检测")
            
            http_services = await self.http_detector.detect_http_services(
                scan_result.target.ip, scan_result.open_ports
            )
            for http_service in http_services:
                scan_result.add_http_service(http_service)
            
            await self._trigger_progress(scan_result.scan_id, "http_detection", 92.0, 
                                       f"✅ HTTP检测完成，发现 {len(http_services)} 个服务")
        
        # Web探测
        if "web_probe" in layers and scan_result.http_services:
            await self._trigger_progress(scan_result.scan_id, "web_probe", 95.0, 
                                       "🕵️ Web深度探测")
            
            admin_directories = await self.web_prober.probe_web_services(scan_result.http_services)
            for admin_dir in admin_directories:
                scan_result.add_admin_directory(admin_dir)
            
            await self._trigger_progress(scan_result.scan_id, "web_probe", 98.0, 
                                       f"✅ Web探测完成，发现 {len(admin_directories)} 个管理目录")
        
        # 标记智能扫描完成
        await self._trigger_progress(scan_result.scan_id, "smart_scan_complete", 100.0, 
                                   "🎉 智能扫描全部完成")
        await self._trigger_callback(scan_result.scan_id, CallbackType.ON_LAYER_COMPLETE, 
                                   ("smart_scan_complete", 100.0))
    
    async def _trigger_callback(self, scan_id: str, callback_type: CallbackType, data: Any) -> None:
        """触发回调函数"""
        if scan_id not in self.scan_callbacks:
            return
        
        callbacks = self.scan_callbacks[scan_id].get(callback_type, [])
        for callback in callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(callback_type, data)
                else:
                    callback(callback_type, data)
            except Exception as e:
                logger.error(f"回调执行失败 {callback_type}: {e}")
    
    async def _trigger_progress(self, scan_id: str, layer: str, progress: float, message: str) -> None:
        """触发进度回调"""
        await self._trigger_callback(scan_id, CallbackType.ON_PROGRESS, {
            "layer": layer,
            "progress": progress,
            "message": message
        })


# ==================== 便捷函数 ====================

# 全局服务实例
_default_service = None

def get_default_service(config: Optional[ScanConfig] = None) -> ScanService:
    """获取默认服务实例"""
    global _default_service
    if _default_service is None:
        _default_service = ScanService(config)
    return _default_service


# 便捷的同步调用函数
def scan(ip: str, ports: Optional[List[int]] = None, layers: Optional[List[str]] = None) -> ScanResult:
    """便捷的同步扫描函数"""
    service = get_default_service()
    return service.scan_sync(ip, ports, layers)


def batch_scan(targets: List[Union[str, ScanTarget]], 
               layers: Optional[List[str]] = None,
               max_concurrent: int = 5) -> List[ScanResult]:
    """便捷的批量扫描函数"""
    service = get_default_service()
    return service.batch_scan_sync(targets, layers, max_concurrent)


# 便捷的异步调用函数
async def scan_async(ip: str, ports: Optional[List[int]] = None, layers: Optional[List[str]] = None) -> ScanResult:
    """便捷的异步扫描函数"""
    service = get_default_service()
    return await service.scan_async(ip, ports, layers)


async def batch_scan_async(targets: List[Union[str, ScanTarget]], 
                          layers: Optional[List[str]] = None,
                          max_concurrent: int = 5) -> List[ScanResult]:
    """便捷的异步批量扫描函数"""
    service = get_default_service()
    return await service.batch_scan_async(targets, layers, max_concurrent) 