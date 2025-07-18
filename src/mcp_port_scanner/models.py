"""
扫描相关的数据模型定义
"""

from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
from enum import Enum
import ipaddress
from datetime import datetime
from dataclasses import dataclass


class ScanStatus(str, Enum):
    """扫描状态枚举"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ServiceProtocol(str, Enum):
    """服务协议枚举"""
    TCP = "tcp"
    UDP = "udp"


class HTTPMethod(str, Enum):
    """HTTP方法枚举"""
    GET = "GET"
    POST = "POST"
    HEAD = "HEAD"
    OPTIONS = "OPTIONS"


class PortInfo(BaseModel):
    """端口信息模型"""
    port: int = Field(..., ge=1, le=65535, description="端口号")
    protocol: ServiceProtocol = Field(default=ServiceProtocol.TCP, description="协议类型")
    state: str = Field(..., description="端口状态 (open/closed/filtered)")
    service: Optional[str] = Field(None, description="服务名称")
    version: Optional[str] = Field(None, description="服务版本")
    banner: Optional[str] = Field(None, description="Banner信息")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="识别置信度")


class HTTPInfo(BaseModel):
    """HTTP服务信息模型"""
    url: str = Field(..., description="HTTP URL")
    status_code: Optional[int] = Field(None, description="HTTP状态码")
    title: Optional[str] = Field(None, description="页面标题")
    server: Optional[str] = Field(None, description="服务器信息")
    headers: Dict[str, str] = Field(default_factory=dict, description="HTTP头部")
    technologies: List[str] = Field(default_factory=list, description="识别的技术栈")
    is_https: bool = Field(default=False, description="是否为HTTPS")
    redirect_url: Optional[str] = Field(None, description="重定向URL")
    content_length: Optional[int] = Field(None, description="内容长度")
    response_time: Optional[float] = Field(None, description="响应时间(秒)")


class DirectoryInfo(BaseModel):
    """目录扫描信息模型"""
    path: str = Field(..., description="目录路径")
    status_code: int = Field(..., description="HTTP状态码")
    content_length: Optional[int] = Field(None, description="内容长度")
    content_type: Optional[str] = Field(None, description="内容类型")
    title: Optional[str] = Field(None, description="页面标题")
    is_admin: bool = Field(default=False, description="是否为管理界面")
    response_time: Optional[float] = Field(None, description="响应时间(秒)")


@dataclass
class ScanTarget:
    """扫描目标"""
    ip: str
    ports: Optional[List[int]] = None
    
    def __repr__(self) -> str:
        """自定义字符串表示，避免输出长端口列表"""
        if self.ports is None:
            return f"ScanTarget(ip='{self.ip}', ports=None)"
        elif len(self.ports) <= 10:
            return f"ScanTarget(ip='{self.ip}', ports={self.ports})"
        else:
            port_preview = self.ports[:5] + ["..."] + self.ports[-2:]
            return f"ScanTarget(ip='{self.ip}', ports=[{', '.join(map(str, port_preview[:5]))}, ..., {', '.join(map(str, port_preview[-2:]))}] ({len(self.ports)} total))"
    
    @property
    def ip_obj(self) -> ipaddress.IPv4Address:
        """获取IP地址对象"""
        return ipaddress.IPv4Address(self.ip)
    
    @property
    def is_private(self) -> bool:
        """判断是否为私有IP"""
        return self.ip_obj.is_private


class ScanResult(BaseModel):
    """扫描结果模型"""
    target: ScanTarget = Field(..., description="扫描目标")
    scan_id: str = Field(..., description="扫描ID")
    status: ScanStatus = Field(default=ScanStatus.PENDING, description="扫描状态")
    start_time: datetime = Field(default_factory=datetime.now, description="开始时间")
    end_time: Optional[datetime] = Field(None, description="结束时间")
    
    # 第一层：基础端口扫描结果
    open_ports: List[PortInfo] = Field(default_factory=list, description="开放端口列表")
    
    # 第二层：HTTP服务识别结果
    http_services: List[HTTPInfo] = Field(default_factory=list, description="HTTP服务列表")
    
    # 第三层：Web深度探测结果
    admin_directories: List[DirectoryInfo] = Field(default_factory=list, description="管理目录列表")
    
    # 元数据
    total_ports_scanned: int = Field(default=0, description="扫描端口总数")
    open_ports_count: int = Field(default=0, description="开放端口数量")
    http_services_count: int = Field(default=0, description="HTTP服务数量")
    scan_duration: Optional[float] = Field(None, description="扫描耗时(秒)")
    error_message: Optional[str] = Field(None, description="错误信息")
    
    def add_port(self, port_info: PortInfo) -> None:
        """添加端口信息"""
        self.open_ports.append(port_info)
        self.open_ports_count = len(self.open_ports)
    
    def add_http_service(self, http_info: HTTPInfo) -> None:
        """添加HTTP服务信息"""
        self.http_services.append(http_info)
        self.http_services_count = len(self.http_services)
    
    def add_admin_directory(self, dir_info: DirectoryInfo) -> None:
        """添加管理目录信息"""
        self.admin_directories.append(dir_info)
    
    def mark_completed(self) -> None:
        """标记扫描完成"""
        self.status = ScanStatus.COMPLETED
        self.end_time = datetime.now()
        if self.start_time:
            self.scan_duration = (self.end_time - self.start_time).total_seconds()
    
    def mark_failed(self, error: str) -> None:
        """标记扫描失败"""
        self.status = ScanStatus.FAILED
        self.end_time = datetime.now()
        self.error_message = error
        if self.start_time:
            self.scan_duration = (self.end_time - self.start_time).total_seconds()


class HTTPDetectionRule(BaseModel):
    """HTTP检测规则模型"""
    name: str = Field(..., description="规则名称")
    description: str = Field(..., description="规则描述")
    banner_patterns: List[str] = Field(..., description="Banner匹配模式")
    port_hints: List[int] = Field(default_factory=list, description="端口提示")
    confidence_boost: float = Field(default=0.1, description="置信度提升")
    priority: int = Field(default=1, description="优先级")


class AdminDirectoryRule(BaseModel):
    """管理目录扫描规则模型"""
    technology: str = Field(..., description="技术栈名称")
    paths: List[str] = Field(..., description="管理路径列表")
    indicators: List[str] = Field(default_factory=list, description="技术栈识别特征")
    priority: int = Field(default=1, description="扫描优先级")


class ScanConfig(BaseModel):
    """扫描配置模型"""
    # 智能扫描模式配置
    smart_scan_enabled: bool = Field(default=True, description="是否启用智能扫描模式")
    smart_scan_threshold: int = Field(default=3, description="智能扫描端口阈值，小于此值执行全端口扫描")
    
    # 预设端口配置
    preset_ports: List[int] = Field(
        default_factory=lambda: [
            # 基础服务端口 (21-1000 由 RustScan 覆盖)
            # 额外常规服务端口
            1433, 3306, 5432, 6379, 27017,  # 数据库
            1521, 5984, 7000, 7001, 9200, 9300,  # 更多数据库
            
            # Web服务端口
            8000, 8001, 8008, 8081, 8082, 8888, 9000, 9090, 9999,
            
            # VPN端口
            1194, 1723, 4500, 51820, 500,
            
            # VNC端口
            5800, 5801, 5802, 5803, 5804, 5805, 5806, 5807, 5808, 5809,
            5900, 5901, 5902, 5903, 5904, 5905, 5906, 5907, 5908, 5909, 5910,
            
            # 远程管理端口
            6568, 5938, 6129, 6130, 6132, 6133, 6783, 6784, 6785, 8040, 8041, 8200,
            
            # 高价值攻击端口
            666, 1080, 1170, 1234, 1243, 1337, 1981, 1999, 2001, 2222, 2989,
            3000, 3024, 3030, 3128, 3129, 3200, 3410, 4000, 4041, 4092, 4444,
            4433, 4567, 4590, 4782, 5000, 5001, 5096, 5321, 5400, 5500, 5556,
            5650, 5651, 5655, 6666, 6667, 7070, 7096, 7443, 7444, 7474, 7687,
            8022, 8848, 8999, 9050, 9051, 9631, 9988, 10002, 10110, 10426,
            10666, 12122, 12345, 12346, 17300, 20034, 21802, 27374, 30662,
            31335, 31337, 31338, 31785, 31789, 35000, 48101, 50050, 53531,
            54320, 55553, 57230, 61466, 65000,
            
            # SNMP, LDAP, Kerberos
            161, 162, 389, 636, 88, 464, 749, 750, 1812, 1813,
            
            # SIP
            5060, 5061,
        ],
        description="预设扫描端口列表，与RustScan 1-1000端口组合使用"
    )
    
    # Web端口配置  
    web_ports: List[int] = Field(
        default_factory=lambda: [80, 443, 8080, 8443, 3000, 4000, 5000, 8000, 8081, 8082, 9000, 9090],
        description="常规Web服务端口列表，用于HTTP服务检测"
    )
    
    # RustScan配置 - 优化性能
    rustscan_timeout: int = Field(default=10000, description="RustScan超时时间(ms) - 平衡速度与准确性")
    rustscan_batch_size: int = Field(default=65535, description="RustScan批处理大小 - 最大并发")
    rustscan_ports: str = Field(default="1-1000", description="RustScan默认扫描端口范围")
    rustscan_tries: int = Field(default=1, description="RustScan重试次数")
    rustscan_ulimit: int = Field(default=8192, description="自动提升文件描述符限制")
    
    # Banner获取配置
    banner_timeout: float = Field(default=5.0, description="Banner获取超时时间(秒)")
    banner_max_bytes: int = Field(default=1024, description="Banner最大字节数")
    
    # HTTP探测配置
    http_timeout: float = Field(default=10.0, description="HTTP请求超时时间(秒)")
    http_max_redirects: int = Field(default=3, description="HTTP最大重定向次数")
    http_user_agent: str = Field(
        default="Mozilla/5.0 (compatible; PortScanner/1.0)",
        description="HTTP User-Agent"
    )
    
    # 目录扫描配置
    admin_scan_enabled: bool = Field(default=True, description="是否启用管理目录扫描")
    admin_scan_threads: int = Field(default=10, description="目录扫描并发数")
    admin_scan_timeout: float = Field(default=5.0, description="目录扫描超时时间(秒)")
    
    # 通用配置
    max_concurrent_targets: int = Field(default=5, description="最大并发扫描目标数")
    enable_logging: bool = Field(default=True, description="是否启用日志")
    log_level: str = Field(default="INFO", description="日志级别")


class ScanRequest(BaseModel):
    """扫描请求模型"""
    targets: List[ScanTarget] = Field(..., description="扫描目标列表")
    config: Optional[ScanConfig] = Field(None, description="扫描配置")
    scan_layers: List[str] = Field(
        default=["port_scan", "http_detection", "web_probe"],
        description="扫描层级"
    )
    callback_url: Optional[str] = Field(None, description="结果回调URL")


class ScanResponse(BaseModel):
    """扫描响应模型"""
    scan_id: str = Field(..., description="扫描ID")
    status: ScanStatus = Field(..., description="扫描状态")
    message: str = Field(..., description="响应消息")
    results: List[ScanResult] = Field(default_factory=list, description="扫描结果列表")
    total_targets: int = Field(default=0, description="目标总数")
    completed_targets: int = Field(default=0, description="已完成目标数")
    estimated_completion: Optional[datetime] = Field(None, description="预计完成时间") 