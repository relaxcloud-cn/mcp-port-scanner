"""
MCP智能分层端口扫描服务

这个包提供了一个基于MCP协议的智能端口扫描服务，
实现分层递进的扫描策略：
1. RustScan基础端口扫描 + Banner获取
2. 基于Banner的智能HTTP服务识别  
3. HTTP服务深度探测 + 管理目录扫描
"""

__version__ = "0.1.0"
__author__ = "Sky"
__email__ = "sky@example.com"

# 导入并初始化日志配置
from .logger_config import logger, configure_logger, init_logger

# 核心业务层
from .scanner import PortScanner
from .http_detector import HTTPDetector
from .web_prober import WebProber

# 统一服务层
from .service import (
    ScanService, ScanProgress, CallbackType,
    get_default_service, scan, batch_scan, scan_async, batch_scan_async
)

# 数据模型
from .models import (
    ScanTarget, ScanConfig, ScanResult, ScanStatus,
    PortInfo, HTTPInfo, DirectoryInfo
)

__all__ = [
    # 核心业务层
    "PortScanner",
    "HTTPDetector", 
    "WebProber",
    
    # 统一服务层
    "ScanService",
    "ScanProgress", 
    "CallbackType",
    "get_default_service",
    "scan",
    "batch_scan", 
    "scan_async",
    "batch_scan_async",
    
    # 数据模型
    "ScanTarget",
    "ScanConfig", 
    "ScanResult",
    "ScanStatus",
    "PortInfo",
    "HTTPInfo",
    "DirectoryInfo",
] 