"""
Python SDK接口
提供面向对象的易用封装
"""

import asyncio
from typing import List, Optional, Union, Dict, Any, Callable
from contextlib import asynccontextmanager

from ..service import ScanService, CallbackType, ScanProgress
from ..models import ScanTarget, ScanConfig, ScanResult
from ..logger_config import logger


class PortScannerSDK:
    """
    端口扫描器Python SDK
    提供简洁易用的Python接口
    """
    
    def __init__(self, config: Optional[ScanConfig] = None):
        """
        初始化SDK
        
        Args:
            config: 扫描配置
        """
        self.service = ScanService(config)
        self._callbacks: Dict[str, Dict[CallbackType, List[Callable]]] = {}
        logger.info("PortScannerSDK: 初始化完成")
        if config:
            logger.debug(f"SDK配置: smart_scan={config.smart_scan_enabled}, threshold={config.smart_scan_threshold}")
    
    # ==================== 基础扫描接口 ====================
    
    def scan(self, ip: str, ports: Optional[List[int]] = None) -> ScanResult:
        """
        扫描单个IP地址
        
        Args:
            ip: 目标IP地址
            ports: 可选端口列表
            
        Returns:
            ScanResult: 扫描结果
            
        Example:
            >>> sdk = PortScannerSDK()
            >>> result = sdk.scan("192.168.1.1")
            >>> print(f"发现 {len(result.open_ports)} 个开放端口")
        """
        logger.info(f"SDK: 执行同步扫描 - IP={ip}, ports={ports}")
        return self.service.scan_sync(ip, ports)
    
    def scan_ports_only(self, ip: str, ports: Optional[List[int]] = None) -> ScanResult:
        """
        仅扫描端口，不进行HTTP检测和Web探测
        
        Args:
            ip: 目标IP地址
            ports: 可选端口列表
            
        Returns:
            ScanResult: 扫描结果
        """
        return self.service.scan_sync(ip, ports, layers=["port_scan"])
    
    def scan_with_http(self, ip: str, ports: Optional[List[int]] = None) -> ScanResult:
        """
        扫描端口并进行HTTP检测，不进行Web探测
        
        Args:
            ip: 目标IP地址
            ports: 可选端口列表
            
        Returns:
            ScanResult: 扫描结果
        """
        return self.service.scan_sync(ip, ports, layers=["port_scan", "http_detection"])
    
    def scan_full(self, ip: str, ports: Optional[List[int]] = None) -> ScanResult:
        """
        完整扫描：端口扫描 + HTTP检测 + Web探测
        
        Args:
            ip: 目标IP地址
            ports: 可选端口列表
            
        Returns:
            ScanResult: 扫描结果
        """
        return self.service.scan_sync(ip, ports, layers=["port_scan", "http_detection", "web_probe"])
    
    # ==================== 批量扫描接口 ====================
    
    def batch_scan(self, 
                   targets: List[Union[str, ScanTarget]], 
                   max_concurrent: int = 5) -> List[ScanResult]:
        """
        批量扫描多个目标
        
        Args:
            targets: 目标列表（IP字符串或ScanTarget对象）
            max_concurrent: 最大并发数
            
        Returns:
            List[ScanResult]: 扫描结果列表
            
        Example:
            >>> sdk = PortScannerSDK()
            >>> targets = ["192.168.1.1", "192.168.1.2", "192.168.1.3"]
            >>> results = sdk.batch_scan(targets)
            >>> for result in results:
            ...     print(f"{result.target.ip}: {len(result.open_ports)} ports")
        """
        return self.service.batch_scan_sync(targets, max_concurrent=max_concurrent)
    
    def scan_network(self, 
                    network: str, 
                    max_concurrent: int = 10) -> List[ScanResult]:
        """
        扫描整个网络段
        
        Args:
            network: 网络段（如 "192.168.1.0/24"）
            max_concurrent: 最大并发数
            
        Returns:
            List[ScanResult]: 扫描结果列表
            
        Example:
            >>> sdk = PortScannerSDK()
            >>> results = sdk.scan_network("192.168.1.0/24")
            >>> active_hosts = [r for r in results if r.open_ports]
            >>> print(f"发现 {len(active_hosts)} 个活跃主机")
        """
        import ipaddress
        
        # 解析网络段
        net = ipaddress.IPv4Network(network, strict=False)
        targets = [str(ip) for ip in net.hosts()]
        
        return self.batch_scan(targets, max_concurrent)
    
    # ==================== 异步接口 ====================
    
    async def scan_async(self, ip: str, ports: Optional[List[int]] = None) -> ScanResult:
        """
        异步扫描单个目标
        
        Args:
            ip: 目标IP地址
            ports: 可选端口列表
            
        Returns:
            ScanResult: 扫描结果
        """
        return await self.service.scan_async(ip, ports)
    
    async def batch_scan_async(self, 
                              targets: List[Union[str, ScanTarget]], 
                              max_concurrent: int = 5) -> List[ScanResult]:
        """
        异步批量扫描
        
        Args:
            targets: 目标列表
            max_concurrent: 最大并发数
            
        Returns:
            List[ScanResult]: 扫描结果列表
        """
        return await self.service.batch_scan_async(targets, max_concurrent=max_concurrent)
    
    # ==================== 进度监控接口 ====================
    
    async def scan_with_progress(self, 
                                ip: str, 
                                ports: Optional[List[int]] = None,
                                progress_callback: Optional[Callable[[ScanProgress], None]] = None) -> ScanResult:
        """
        扫描并监控进度
        
        Args:
            ip: 目标IP地址
            ports: 可选端口列表
            progress_callback: 进度回调函数
            
        Returns:
            ScanResult: 扫描结果
            
        Example:
            >>> async def progress_handler(progress):
            ...     print(f"进度: {progress.progress_percent:.1f}% - {progress.message}")
            >>> 
            >>> sdk = PortScannerSDK()
            >>> result = await sdk.scan_with_progress("192.168.1.1", progress_callback=progress_handler)
        """
        result = None
        
        async for progress in self.service.scan_stream(ip, ports):
            if progress_callback:
                progress_callback(progress)
            
            # 获取最终结果
            if progress.progress_percent >= 100.0:
                result = self.service.get_scan_result(progress.scan_id)
        
        return result
    
    # ==================== 回调接口 ====================
    
    def on_scan_start(self, callback: Callable[[ScanResult], None]) -> 'PortScannerSDK':
        """
        注册扫描开始回调
        
        Args:
            callback: 回调函数
            
        Returns:
            self: 支持链式调用
        """
        return self._register_global_callback(CallbackType.ON_START, callback)
    
    def on_scan_complete(self, callback: Callable[[ScanResult], None]) -> 'PortScannerSDK':
        """
        注册扫描完成回调
        
        Args:
            callback: 回调函数
            
        Returns:
            self: 支持链式调用
        """
        return self._register_global_callback(CallbackType.ON_COMPLETE, callback)
    
    def on_scan_error(self, callback: Callable[[Exception], None]) -> 'PortScannerSDK':
        """
        注册扫描错误回调
        
        Args:
            callback: 回调函数
            
        Returns:
            self: 支持链式调用
        """
        return self._register_global_callback(CallbackType.ON_ERROR, callback)
    
    async def scan_with_callbacks(self, 
                                 ip: str, 
                                 ports: Optional[List[int]] = None) -> str:
        """
        使用已注册回调的异步扫描
        
        Args:
            ip: 目标IP地址
            ports: 可选端口列表
            
        Returns:
            str: 扫描ID
        """
        return await self.service.scan_with_callbacks(ip, ports, callbacks=self._callbacks.get("global", {}))
    
    # ==================== 配置管理 ====================
    
    def configure(self, **kwargs) -> 'PortScannerSDK':
        """
        配置扫描参数
        
        Args:
            **kwargs: 配置参数
            
        Returns:
            self: 支持链式调用
            
        Example:
            >>> sdk = PortScannerSDK().configure(
            ...     rustscan_timeout=5000,
            ...     admin_scan_enabled=False
            ... )
        """
        current_config = self.service.get_config()
        
        # 更新配置
        config_dict = current_config.dict()
        config_dict.update(kwargs)
        
        new_config = ScanConfig(**config_dict)
        self.service.update_config(new_config)
        
        return self
    
    def set_timeout(self, timeout: int) -> 'PortScannerSDK':
        """设置RustScan超时时间"""
        return self.configure(rustscan_timeout=timeout)
    
    def disable_admin_scan(self) -> 'PortScannerSDK':
        """禁用管理目录扫描"""
        return self.configure(admin_scan_enabled=False)
    
    def enable_admin_scan(self) -> 'PortScannerSDK':
        """启用管理目录扫描"""
        return self.configure(admin_scan_enabled=True)
    
    # ==================== 便捷查询接口 ====================
    
    def get_open_ports(self, ip: str) -> List[int]:
        """
        快速获取开放端口列表
        
        Args:
            ip: 目标IP地址
            
        Returns:
            List[int]: 开放端口列表
        """
        result = self.scan_ports_only(ip)
        return [port.port for port in result.open_ports]
    
    def get_http_services(self, ip: str) -> List[str]:
        """
        快速获取HTTP服务URL列表
        
        Args:
            ip: 目标IP地址
            
        Returns:
            List[str]: HTTP服务URL列表
        """
        result = self.scan_with_http(ip)
        return [http.url for http in result.http_services]
    
    def get_admin_interfaces(self, ip: str) -> List[str]:
        """
        快速获取管理界面URL列表
        
        Args:
            ip: 目标IP地址
            
        Returns:
            List[str]: 管理界面URL列表
        """
        result = self.scan_full(ip)
        admin_urls = []
        
        for http_service in result.http_services:
            base_url = http_service.url
            for directory in result.admin_directories:
                if directory.is_admin:
                    admin_urls.append(f"{base_url.rstrip('/')}{directory.path}")
        
        return admin_urls
    
    def is_host_alive(self, ip: str) -> bool:
        """
        检查主机是否存活（是否有开放端口）
        
        Args:
            ip: 目标IP地址
            
        Returns:
            bool: 主机是否存活
        """
        result = self.scan_ports_only(ip)
        return len(result.open_ports) > 0
    
    # ==================== 上下文管理器 ====================
    
    @asynccontextmanager
    async def async_session(self):
        """
        异步上下文管理器
        
        Example:
            >>> async with sdk.async_session() as session:
            ...     result1 = await session.scan_async("192.168.1.1")
            ...     result2 = await session.scan_async("192.168.1.2")
        """
        yield self
    
    # ==================== 内部辅助方法 ====================
    
    def _register_global_callback(self, callback_type: CallbackType, callback: Callable) -> 'PortScannerSDK':
        """注册全局回调"""
        if "global" not in self._callbacks:
            self._callbacks["global"] = {ct: [] for ct in CallbackType}
        
        self._callbacks["global"][callback_type].append(callback)
        return self
    
    # ==================== 状态查询 ====================
    
    def get_active_scans(self) -> List[ScanResult]:
        """获取活跃扫描列表"""
        return self.service.list_active_scans()
    
    def get_scan_result(self, scan_id: str) -> Optional[ScanResult]:
        """根据扫描ID获取结果"""
        return self.service.get_scan_result(scan_id)


# ==================== 便捷函数 ====================

def quick_scan(ip: str, ports: Optional[List[int]] = None) -> ScanResult:
    """
    快速扫描函数
    
    Args:
        ip: 目标IP地址
        ports: 可选端口列表
        
    Returns:
        ScanResult: 扫描结果
        
    Example:
        >>> from mcp_port_scanner import quick_scan
        >>> result = quick_scan("192.168.1.1")
        >>> print(f"开放端口: {[p.port for p in result.open_ports]}")
    """
    sdk = PortScannerSDK()
    return sdk.scan(ip, ports)


def scan_network_quick(network: str, max_concurrent: int = 10) -> List[ScanResult]:
    """
    快速网络扫描函数
    
    Args:
        network: 网络段（如 "192.168.1.0/24"）
        max_concurrent: 最大并发数
        
    Returns:
        List[ScanResult]: 扫描结果列表
        
    Example:
        >>> from mcp_port_scanner import scan_network_quick
        >>> results = scan_network_quick("192.168.1.0/24")
        >>> active_hosts = [r.target.ip for r in results if r.open_ports]
        >>> print(f"活跃主机: {active_hosts}")
    """
    sdk = PortScannerSDK()
    return sdk.scan_network(network, max_concurrent) 