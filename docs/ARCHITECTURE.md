# MCP智能端口扫描器 - 架构设计

## 设计理念

### 1. 分层递进扫描

传统端口扫描器通常采用"一刀切"的方式，要么全端口扫描（慢），要么只扫常用端口（可能遗漏）。本项目采用**分层递进**的设计理念：

```
Layer 1: 端口发现
  ↓ (智能决策)
Layer 2: HTTP服务识别  
  ↓ (条件过滤)
Layer 3: Web深度探测
```

每一层都基于上一层的结果进行智能决策，实现效率和覆盖率的平衡。

### 2. 智能扫描策略

核心创新：**动态扫描深度调整**

```python
if 开放端口数 < 阈值(默认3):
    # 端口少，可能有隐藏服务
    执行全端口深度扫描
else:
    # 端口多，已经足够了解目标
    跳过全端口扫描，专注Web检测
```

这种策略基于实际经验：
- 安全意识强的服务器往往只开放少量必要端口
- 开放大量端口的服务器通常已经暴露了足够信息

### 3. 模块化架构

采用清晰的分层架构，每层职责单一：

- **接口层**：处理不同协议（MCP、HTTP、CLI）
- **适配器层**：协议转换和数据格式化
- **服务层**：业务逻辑编排和流程控制
- **业务层**：具体扫描功能实现

## 核心架构

### 整体架构图

```
┌─────────────────────────────────────────────────────────┐
│                    用户交互层                             │
│         Cursor / CLI / Web UI / API Client              │
└─────────────┬───────────────┬──────────────┬────────────┘
              │               │              │
              ▼               ▼              ▼
┌─────────────────────────────────────────────────────────┐
│                    接口层 (Interfaces)                    │
├─────────────┬──────────────┬──────────────┬─────────────┤
│   CLI接口   │  MCP Server  │  HTTP/SSE   │  Cursor SSE │
│  命令行交互  │  标准MCP协议  │  Web API    │  编辑器集成  │
└─────────────┴──────────────┴──────────────┴─────────────┘
              │               │              │
              ▼               ▼              ▼
┌─────────────────────────────────────────────────────────┐
│                   适配器层 (Adapters)                     │
│   请求转换 │ 响应格式化 │ 流式处理 │ 错误处理           │
└─────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────┐
│                  服务层 (Service Layer)                   │
│                     ScanService                          │
│  • 扫描流程编排    • 并发控制      • 任务管理           │
│  • 智能决策引擎    • 结果聚合      • 状态追踪           │
└─────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
┌─────────────────────────────────────────────────────────┐
│                  业务层 (Business Layer)                  │
├─────────────┬──────────────┬──────────────┬─────────────┤
│PortScanner  │ HTTPDetector │  WebProber   │   Models    │
│• RustScan   │• Banner分析  │• 目录扫描    │• 数据模型   │
│• Banner获取  │• HTTP验证    │• 管理界面    │• 配置管理   │
└─────────────┴──────────────┴──────────────┴─────────────┘
```

### 数据流向

```
1. 用户请求
   ↓
2. 接口层接收（MCP/HTTP/CLI）
   ↓
3. 适配器转换为统一格式
   ↓
4. 服务层编排扫描流程
   ↓
5. 业务层执行具体扫描
   ↓
6. 结果逐层返回
   ↓
7. 适配器格式化输出
   ↓
8. 接口层响应用户
```

## 关键设计决策

### 1. 为什么选择MCP协议？

MCP（Model Context Protocol）是Anthropic提出的标准化AI工具协议：

**优势**：
- 标准化的工具定义和调用方式
- 与AI助手无缝集成
- 支持流式响应
- 跨平台兼容

**实现方式**：
```python
@server.list_tools()
async def list_tools() -> List[Tool]:
    return [
        Tool(
            name="scan_target",
            description="智能扫描目标",
            inputSchema={...}
        )
    ]
```

### 2. 异步架构设计

全面采用Python异步编程（asyncio）：

**并发模型**：
```python
# 端口扫描：外部进程（RustScan）
# Banner获取：asyncio + 信号量控制
# HTTP检测：httpx异步客户端
# 目录扫描：并发协程池
```

**性能优化**：
- RustScan：65535并发连接
- Banner：100并发TCP连接
- HTTP：连接池复用
- 目录扫描：10线程并发

### 3. 适配器模式

为什么使用适配器模式？

```python
class BaseAdapter(ABC):
    @abstractmethod
    async def handle_request(self, request_data: Dict[str, Any]) -> Any:
        """处理请求"""
        pass
```

**好处**：
- 解耦接口和业务逻辑
- 易于添加新接口
- 统一的错误处理
- 格式转换集中管理

### 4. 智能规则引擎

HTTP检测和Web探测都采用规则引擎：

```python
class HTTPDetectionRule:
    name: str                    # 规则名称
    banner_patterns: List[str]   # Banner匹配模式
    port_hints: List[int]        # 端口提示
    confidence_boost: float      # 置信度加成
    priority: int               # 优先级
```

**匹配流程**：
1. Banner模式匹配（正则）
2. 端口提示权重
3. 置信度累加
4. 阈值判断

## 核心组件详解

### 1. ScanService（服务编排层）

**职责**：
- 扫描流程编排
- 并发控制
- 进度追踪
- 结果聚合

**关键方法**：
```python
async def _execute_smart_scan(self, scan_result: ScanResult, layers: List[str]) -> None:
    # 1. 预设端口扫描
    port_infos = await self._scan_preset_ports(scan_result.target)
    
    # 2. 智能决策
    if len(port_infos) < self.config.smart_scan_threshold:
        # 执行全端口扫描
        all_ports = await self._execute_full_port_scan(scan_result.target)
    
    # 3. HTTP检测
    if "http_detection" in layers:
        http_services = await self._detect_http_services(port_infos)
    
    # 4. Web探测
    if "web_probe" in layers and http_services:
        admin_dirs = await self._probe_web_services(http_services)
```

### 2. PortScanner（端口扫描器）

**技术选型**：
- RustScan：Rust编写的超快端口扫描器
- 原因：比Nmap快10倍，内存占用小

**扫描流程**：
```
1. RustScan端口发现
   ├─ 命令：rustscan -a {ip} -p {ports} -t {timeout}
   └─ 输出：开放端口列表

2. Banner信息获取
   ├─ TCP连接到每个开放端口
   ├─ 发送探测数据
   └─ 接收Banner响应

3. 服务识别
   ├─ 基于端口号
   ├─ 基于Banner内容
   └─ 基于响应特征
```

### 3. HTTPDetector（HTTP检测器）

**智能识别算法**：

```python
置信度计算：
1. 基础分值：
   - 端口是80/443/8080等：+0.5
   - 服务标记为http/https：+0.5

2. Banner匹配：
   - 包含"HTTP/1.1"：+0.3
   - 包含"Server:"：+0.4
   - 包含Web服务器名：+0.3

3. 阈值判断：
   - 总分 >= 0.3：识别为HTTP服务
```

### 4. WebProber（Web探测器）

**探测策略**：

```python
规则分类：
1. 通用规则（Generic）
   - /admin, /login, /manage
   - 适用于所有HTTP服务

2. 技术栈规则（Technology-specific）
   - Tomcat: /manager/html
   - WordPress: /wp-admin
   - 基于HTTP响应特征选择

3. 优先级控制
   - Priority 1: 管理界面
   - Priority 2: 状态页面
   - Priority 3: 备份文件
```

## 性能优化策略

### 1. 分阶段超时控制

```python
超时配置：
- RustScan: 500ms（极速）
- Banner: 5s（适中）
- HTTP: 10s（宽松）
- 目录扫描: 5s（适中）
```

### 2. 智能跳过机制

```python
跳过条件：
- 非HTTP端口跳过HTTP检测
- 无HTTP服务跳过Web探测
- 404响应跳过深度扫描
```

### 3. 结果缓存

```python
缓存策略：
- 扫描结果内存缓存
- Banner信息复用
- HTTP连接池
```

## 扩展性设计

### 1. 插件化扫描器

添加新扫描器只需：
1. 继承基类
2. 实现扫描方法
3. 注册到服务层

```python
class CustomScanner:
    async def scan_custom(self, target: str) -> List[CustomInfo]:
        # 实现自定义扫描
        pass
```

### 2. 规则热加载

支持从配置文件加载规则：
```toml
[[http_rules]]
name = "Custom Service"
patterns = ["CustomServer/*"]
confidence = 0.5
```

### 3. 接口扩展

添加新接口只需：
1. 创建适配器
2. 实现接口层
3. 注册路由

## 安全考虑

### 1. 输入验证

```python
- IP地址格式验证
- 端口范围检查
- 扫描速率限制
- 并发数量控制
```

### 2. 资源限制

```python
- 最大并发扫描数
- 内存使用上限
- 文件描述符限制
- 超时强制中断
```

### 3. 日志脱敏

```python
- 不记录完整Banner
- 不保存认证信息
- 可配置日志级别
```

## 未来演进

### 1. 短期计划

- [ ] 服务指纹库扩充
- [ ] 漏洞检测集成
- [ ] 分布式扫描支持
- [ ] Web UI界面

### 2. 长期愿景

- [ ] AI驱动的智能决策
- [ ] 自动化渗透测试
- [ ] 威胁情报集成
- [ ] 云原生架构

---

本架构设计持续演进中，欢迎贡献想法和代码。 