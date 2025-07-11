# MCP智能端口扫描器 - 开发文档

## 目录

1. [项目概述](#项目概述)
2. [技术架构](#技术架构)
3. [核心组件](#核心组件)
4. [数据模型](#数据模型)
5. [接口协议](#接口协议)
6. [扩展开发](#扩展开发)
7. [性能优化](#性能优化)
8. [部署指南](#部署指南)

## 项目概述

MCP智能端口扫描器是一个基于MCP（Model Context Protocol）协议的分层递进式端口扫描服务。该项目实现了智能扫描策略，能够根据扫描结果动态调整扫描深度，提供高效准确的网络服务发现能力。

### 核心特性

- **智能扫描模式**：根据端口数量动态决定扫描策略
- **分层递进架构**：端口扫描 → HTTP检测 → Web深度探测
- **多接口支持**：MCP协议（stdio）、HTTP/SSE、Cursor优化接口
- **并发优化**：高性能异步扫描，支持批量和网段扫描
- **实时反馈**：SSE推送进度，阶段性结果展示

### 技术栈

- **语言**：Python 3.12+
- **异步框架**：asyncio
- **Web框架**：FastAPI
- **HTTP客户端**：httpx
- **端口扫描**：RustScan（外部工具）
- **协议支持**：MCP SDK、SSE（Server-Sent Events）

## 技术架构

### 整体架构图

```
┌─────────────────────────────────────────────────────────┐
│                    接口层 (Interfaces)                    │
├─────────────┬──────────────┬──────────────┬─────────────┤
│  CLI接口    │  MCP Server  │  HTTP/SSE   │  Cursor SSE │
│ (cli.py)    │ (mcp_server) │ (http_sse)  │ (cursor)    │
├─────────────┴──────────────┴──────────────┴─────────────┤
│                   适配器层 (Adapters)                     │
├─────────────┬──────────────┬──────────────┬─────────────┤
│ CLI适配器   │ MCP本地适配器 │ MCP远程适配器│ SSE适配器   │
├─────────────┴──────────────┴──────────────┴─────────────┤
│                  服务层 (Service Layer)                   │
│                     ScanService                          │
├──────────────────────────────────────────────────────────┤
│                  业务层 (Business Layer)                  │
├─────────────┬──────────────┬──────────────┬─────────────┤
│ PortScanner │ HTTPDetector │  WebProber   │   Models    │
│ (第一层)    │   (第二层)    │   (第三层)    │  (数据模型) │
└─────────────┴──────────────┴──────────────┴─────────────┘
```

### 分层扫描流程

```
1. 端口扫描层（PortScanner）
   ├─ RustScan快速端口发现
   ├─ Banner信息获取
   └─ 智能决策：少端口→全端口扫描

2. HTTP检测层（HTTPDetector）
   ├─ 基于Banner的智能识别
   ├─ HTTP/HTTPS服务验证
   └─ 服务器信息提取

3. Web探测层（WebProber）
   ├─ 管理界面发现
   ├─ 技术栈特定路径扫描
   └─ 深度目录探测
```

## 核心组件

### 1. ScanService（统一服务层）

`src/mcp_port_scanner/service.py`

核心服务类，提供统一的扫描接口：

```python
class ScanService:
    """统一的端口扫描服务"""
    
    # 同步接口
    def scan_sync(ip: str, ports: Optional[List[int]] = None) -> ScanResult
    def batch_scan_sync(targets: List[str]) -> List[ScanResult]
    
    # 异步接口
    async def scan_async(ip: str, ports: Optional[List[int]] = None) -> ScanResult
    async def batch_scan_async(targets: List[str]) -> List[ScanResult]
    
    # 流式接口
    async def scan_async_with_progress(ip: str, progress_callback: Callable) -> ScanResult
    
    # 任务管理
    def get_scan_status(scan_id: str) -> ScanStatus
    def list_active_scans() -> List[str]
```

**智能扫描逻辑**：
- 预设端口扫描（1-1000 + 常用端口）
- 发现端口数 < 阈值（默认3）→ 执行全端口扫描
- 发现端口数 ≥ 阈值 → 跳过全端口，直接Web检测

### 2. PortScanner（第一层扫描）

`src/mcp_port_scanner/scanner.py`

基于RustScan的高速端口扫描器：

```python
class PortScanner:
    """端口扫描器 - 第一层扫描功能"""
    
    async def scan_target(target: ScanTarget) -> List[PortInfo]
    async def _rustscan_ports(target: ScanTarget) -> List[int]
    async def _grab_banners(ip: str, ports: List[int]) -> List[PortInfo]
```

**关键特性**：
- RustScan集成：极速端口发现
- 智能Banner获取：TCP连接获取服务信息
- 并发优化：异步Banner抓取

### 3. HTTPDetector（第二层检测）

`src/mcp_port_scanner/http_detector.py`

智能HTTP服务识别器：

```python
class HTTPDetector:
    """HTTP服务检测器 - 第二层检测功能"""
    
    async def detect_http_services(ip: str, port_infos: List[PortInfo]) -> List[HTTPInfo]
    def _identify_http_candidates(port_infos: List[PortInfo]) -> List[PortInfo]
    async def _verify_http_services(ip: str, candidates: List[PortInfo]) -> List[HTTPInfo]
```

**检测规则引擎**：
- Banner模式匹配
- 端口提示权重
- 置信度评分系统
- HTTP/HTTPS自动识别

### 4. WebProber（第三层探测）

`src/mcp_port_scanner/web_prober.py`

Web应用深度探测器：

```python
class WebProber:
    """Web深度探测器 - 第三层探测功能"""
    
    async def probe_web_services(http_services: List[HTTPInfo]) -> List[DirectoryInfo]
    def _select_applicable_rules(http_service: HTTPInfo) -> List[AdminDirectoryRule]
    async def _scan_directories(base_url: str, paths: List[str]) -> List[DirectoryInfo]
```

**探测规则库**：
- 通用管理路径
- 技术栈特定路径（Tomcat、WebLogic、Jenkins等）
- 智能规则匹配
- 并发目录扫描

## 数据模型

### 核心模型

```python
# 扫描目标
class ScanTarget(BaseModel):
    ip: str
    ports: Optional[List[int]] = None

# 扫描配置
class ScanConfig(BaseModel):
    # 智能扫描配置
    smart_scan_enabled: bool = True
    smart_scan_threshold: int = 3
    
    # 预设端口
    preset_ports: List[int] = [...]
    web_ports: List[int] = [80, 443, 8080, ...]
    
    # RustScan配置
    rustscan_timeout: int = 500
    rustscan_batch_size: int = 65535
    
    # HTTP配置
    http_timeout: float = 10.0
    http_user_agent: str = "..."

# 扫描结果
class ScanResult(BaseModel):
    target: ScanTarget
    scan_id: str
    status: ScanStatus
    
    # 分层结果
    open_ports: List[PortInfo]
    http_services: List[HTTPInfo]
    admin_directories: List[DirectoryInfo]
```

### 信息模型

```python
# 端口信息
class PortInfo(BaseModel):
    port: int
    protocol: str = "tcp"
    state: str = "open"
    service: Optional[str] = None
    version: Optional[str] = None
    banner: Optional[str] = None

# HTTP服务信息
class HTTPInfo(BaseModel):
    url: str
    status_code: int
    headers: Dict[str, str]
    title: Optional[str] = None
    server: Optional[str] = None
    is_https: bool = False

# 目录信息
class DirectoryInfo(BaseModel):
    path: str
    status_code: int
    title: Optional[str] = None
    is_admin: bool = False
```

## 接口协议

### 1. MCP工具接口

标准MCP协议工具定义：

```python
# scan_target - 扫描单个目标
{
    "name": "scan_target",
    "parameters": {
        "ip": "192.168.1.1",
        "ports": [80, 443],  # 可选
        "scan_layers": ["port_scan", "http_detection", "web_probe"],
        "config": {...}  # 可选配置
    }
}

# batch_scan - 批量扫描
{
    "name": "batch_scan",
    "parameters": {
        "targets": ["192.168.1.1", "192.168.1.2"],
        "scan_layers": [...],
        "max_concurrent": 5
    }
}

# get_scan_status - 查询状态
{
    "name": "get_scan_status",
    "parameters": {
        "scan_id": "uuid-xxx"
    }
}
```

### 2. HTTP/SSE接口

RESTful API + Server-Sent Events：

```http
# 启动扫描
POST /scan
{
    "target": "192.168.1.1",
    "ports": [80, 443],
    "scan_layers": ["port_scan", "http_detection", "web_probe"]
}

# SSE实时进度
GET /scan/{scan_id}/stream
Content-Type: text/event-stream

data: {"type": "progress", "data": {...}}
data: {"type": "layer_complete", "data": {...}}
data: {"type": "complete", "data": {...}}

# 查询结果
GET /scan/{scan_id}/result
```

### 3. Cursor优化接口

针对Cursor编辑器优化的SSE接口：

```http
# Cursor扫描
POST /cursor/scan
{
    "ip": "192.168.1.1",
    "real_time": true,
    "config": {...}
}

# Cursor SSE流（0.5秒更新频率）
GET /cursor/scan/{scan_id}/stream

data: {"type": "start", "timestamp": "...", "data": {...}}
data: {"type": "progress", "timestamp": "...", "data": {...}}
data: {"type": "complete", "timestamp": "...", "data": {...}}
```

## 扩展开发

### 1. 添加新的扫描层

创建新的扫描器类：

```python
# src/mcp_port_scanner/custom_scanner.py
from .models import BaseModel

class CustomScanner:
    """自定义扫描器"""
    
    def __init__(self, config: Optional[ScanConfig] = None):
        self.config = config or ScanConfig()
    
    async def scan_custom(self, target: str) -> List[CustomInfo]:
        """执行自定义扫描"""
        # 实现扫描逻辑
        pass
```

在服务层注册：

```python
# service.py
self.custom_scanner = CustomScanner(self.config)

# 在扫描流程中调用
if "custom_scan" in layers:
    custom_results = await self.custom_scanner.scan_custom(target)
```

### 2. 添加新的检测规则

扩展检测规则：

```python
# 在 http_detector.py 中添加
HTTPDetectionRule(
    name="Custom Service",
    banner_patterns=[r"CustomServer/\d+"],
    port_hints=[9999],
    confidence_boost=0.3,
    priority=1
)

# 在 web_prober.py 中添加
AdminDirectoryRule(
    technology="CustomApp",
    paths=["/custom-admin", "/custom-panel"],
    indicators=["custom-header"],
    priority=1
)
```

### 3. 自定义适配器

实现新的接口适配器：

```python
# adapters/custom_adapter.py
from . import BaseAdapter

class CustomAdapter(BaseAdapter):
    async def handle_request(self, request_data: Dict[str, Any]) -> Any:
        # 处理请求
        pass
    
    def format_response(self, result: ScanResult) -> Any:
        # 格式化响应
        pass
```

## 性能优化

### 1. 扫描性能优化

**RustScan参数调优**：
```python
rustscan_timeout=200      # 极速超时
rustscan_batch_size=65535 # 最大并发
rustscan_ulimit=8192      # 文件描述符限制
```

**并发控制**：
- 端口扫描：RustScan内部并发
- Banner获取：asyncio并发（信号量控制）
- HTTP检测：httpx异步客户端池
- 目录扫描：线程池 + 信号量

### 2. 智能扫描策略

**阈值优化**：
- 默认阈值：3个端口
- 小于阈值：深度扫描（全端口）
- 大于阈值：快速模式（跳过全端口）

**端口优先级**：
- 预设端口：1-1000 + 常用服务端口
- Web端口：优先HTTP服务检测
- 高价值端口：管理界面、数据库等

### 3. 资源管理

**内存优化**：
- 流式处理大量结果
- 结果缓存限制
- Banner长度限制

**连接管理**：
- HTTP连接池复用
- 超时控制
- 错误重试机制

## 部署指南

### 1. Docker部署

```dockerfile
FROM python:3.12-slim

# 安装RustScan
RUN apt-get update && \
    apt-get install -y wget && \
    wget https://github.com/RustScan/RustScan/releases/download/2.0.1/rustscan_2.0.1_amd64.deb && \
    dpkg -i rustscan_2.0.1_amd64.deb

# 安装Python依赖
COPY requirements.txt .
RUN pip install -r requirements.txt

# 复制代码
COPY . /app
WORKDIR /app

# 启动服务
CMD ["python", "-m", "mcp_port_scanner.mcp_server"]
```

### 2. 系统要求

**最低配置**：
- CPU：2核
- 内存：2GB
- 存储：1GB
- 网络：100Mbps

**推荐配置**：
- CPU：4核+
- 内存：4GB+
- 存储：10GB（日志存储）
- 网络：1Gbps

### 3. 配置文件

`config/default.toml`：
```toml
[scan]
smart_scan_enabled = true
smart_scan_threshold = 3

[rustscan]
timeout = 500
batch_size = 65535

[http]
timeout = 10.0
max_redirects = 3

[logging]
enabled = true
level = "INFO"
```

## 开发最佳实践

### 1. 代码规范

- 使用类型注解
- 遵循PEP 8规范
- 完整的文档字符串
- 异步函数命名：`_async`后缀

### 2. 错误处理

```python
try:
    result = await scanner.scan_target(target)
except asyncio.TimeoutError:
    logger.error(f"扫描超时: {target}")
except Exception as e:
    logger.exception(f"扫描失败: {target}")
    # 优雅降级处理
```

### 3. 日志规范

```python
logger.info(f"开始扫描: {target}")     # 关键操作
logger.debug(f"端口详情: {port_info}") # 调试信息
logger.warning(f"连接失败: {url}")     # 警告
logger.error(f"扫描失败: {error}")     # 错误
```

### 4. 测试建议

- 单元测试：核心业务逻辑
- 集成测试：完整扫描流程
- 性能测试：并发和延迟
- 安全测试：输入验证

## 常见问题

### Q1: 如何调整扫描速度？

调整RustScan参数和并发数：
```python
config = ScanConfig(
    rustscan_timeout=1000,      # 增加超时
    rustscan_batch_size=10000,  # 减少并发
    max_concurrent_targets=3    # 减少目标并发
)
```

### Q2: 如何添加自定义端口？

修改配置中的预设端口：
```python
config = ScanConfig(
    preset_ports=[22, 80, 443, 3306, 6379, 自定义端口...]
)
```

### Q3: 如何禁用某个扫描层？

在scan_layers参数中排除：
```python
# 只进行端口扫描
layers = ["port_scan"]

# 跳过Web探测
layers = ["port_scan", "http_detection"]
```

---

本文档持续更新中，最新版本请查看项目仓库。 