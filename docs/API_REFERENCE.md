# MCP端口扫描器 - API参考文档

## MCP工具列表

### 1. scan_target - 智能扫描单个目标

对单个IP地址进行分层递进端口扫描，支持智能扫描模式。

**参数**：
- `ip` (string, required): 目标IP地址
- `ports` (array[int], optional): 指定端口列表，不指定则使用智能扫描
- `scan_layers` (array[string], optional): 扫描层级，默认 ["port_scan", "http_detection", "web_probe"]
- `config` (object, optional): 自定义扫描配置

**示例**：

```json
// 智能扫描（推荐）
{
  "ip": "192.168.1.100"
}

// 指定端口扫描
{
  "ip": "192.168.1.100",
  "ports": [80, 443, 8080, 3306]
}

// 仅端口扫描
{
  "ip": "192.168.1.100",
  "scan_layers": ["port_scan"]
}

// 完整配置示例
{
  "ip": "192.168.1.100",
  "ports": null,
  "scan_layers": ["port_scan", "http_detection", "web_probe"],
  "config": {
    "smart_scan_threshold": 5,
    "rustscan_timeout": 1000,
    "http_timeout": 15.0,
    "admin_scan_enabled": true
  }
}
```

**返回结果**：

```json
{
  "scan_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "target": "192.168.1.100",
  "summary": {
    "total_ports_scanned": 65535,
    "open_ports_count": 5,
    "http_services_count": 3,
    "admin_interfaces_found": 2,
    "scan_duration": 45.2
  },
  "open_ports": [
    {
      "port": 22,
      "protocol": "tcp",
      "service": "ssh",
      "version": "OpenSSH_8.2p1",
      "banner": "SSH-2.0-OpenSSH_8.2p1 Ubuntu-4ubuntu0.5"
    },
    {
      "port": 80,
      "protocol": "tcp",
      "service": "http",
      "banner": "HTTP/1.1 200 OK\\r\\nServer: nginx/1.18.0"
    }
  ],
  "http_services": [
    {
      "url": "http://192.168.1.100:80/",
      "status_code": 200,
      "title": "Welcome to nginx!",
      "server": "nginx/1.18.0",
      "is_https": false,
      "response_time": 0.123
    },
    {
      "url": "https://192.168.1.100:443/",
      "status_code": 200,
      "title": "Secure Site",
      "server": "nginx/1.18.0",
      "is_https": true
    }
  ],
  "admin_directories": [
    {
      "path": "/admin",
      "status_code": 401,
      "title": "401 Authorization Required",
      "is_admin": true
    },
    {
      "path": "/phpmyadmin",
      "status_code": 200,
      "title": "phpMyAdmin",
      "is_admin": true
    }
  ]
}
```

### 2. batch_scan - 批量扫描多个目标

批量扫描多个IP地址，支持并发控制。

**参数**：
- `targets` (array[string], required): IP地址列表
- `scan_layers` (array[string], optional): 扫描层级
- `max_concurrent` (int, optional): 最大并发数，默认5
- `config` (object, optional): 扫描配置

**示例**：

```json
// 基础批量扫描
{
  "targets": ["192.168.1.1", "192.168.1.2", "192.168.1.3"]
}

// 带配置的批量扫描
{
  "targets": ["10.0.0.1", "10.0.0.2", "10.0.0.3", "10.0.0.4", "10.0.0.5"],
  "scan_layers": ["port_scan", "http_detection"],
  "max_concurrent": 3,
  "config": {
    "smart_scan_enabled": false,
    "rustscan_timeout": 500
  }
}
```

**返回结果**：

```json
{
  "batch_id": "batch_550e8400",
  "status": "completed",
  "total_targets": 3,
  "completed_targets": 3,
  "failed_targets": 0,
  "results": [
    {
      "target": "192.168.1.1",
      "scan_id": "scan_001",
      "status": "completed",
      "open_ports_count": 5,
      "http_services_count": 2
    },
    {
      "target": "192.168.1.2",
      "scan_id": "scan_002",
      "status": "completed",
      "open_ports_count": 3,
      "http_services_count": 1
    }
  ],
  "duration": 120.5
}
```

### 3. quick_scan - 快速端口扫描

仅执行端口扫描，不进行HTTP检测和Web探测，适合快速了解端口开放情况。

**参数**：
- `ip` (string, required): 目标IP地址
- `ports` (array[int], optional): 指定端口列表

**示例**：

```json
// 快速扫描常用端口
{
  "ip": "192.168.1.100"
}

// 快速扫描指定端口
{
  "ip": "192.168.1.100",
  "ports": [22, 80, 443, 3306, 6379, 9200]
}
```

**返回结果**：

```json
{
  "scan_id": "quick_550e8400",
  "target": "192.168.1.100",
  "open_ports": [
    {
      "port": 22,
      "service": "ssh",
      "banner": "SSH-2.0-OpenSSH_8.2p1"
    },
    {
      "port": 80,
      "service": "http",
      "banner": "HTTP/1.1 200 OK"
    }
  ],
  "scan_time": 5.2
}
```

### 4. scan_network - 扫描网络段（C段）

扫描整个C段网络，自动识别活跃主机并进行端口扫描。

**参数**：
- `network` (string, required): 网络段，格式如 "192.168.1.0/24"
- `scan_layers` (array[string], optional): 扫描层级
- `max_concurrent` (int, optional): 最大并发数
- `skip_host_discovery` (bool, optional): 是否跳过主机发现，默认false

**示例**：

```json
// 扫描C段
{
  "network": "192.168.1.0/24"
}

// 带配置的网段扫描
{
  "network": "10.0.0.0/24",
  "scan_layers": ["port_scan"],
  "max_concurrent": 10,
  "skip_host_discovery": false
}
```

**返回结果**：

```json
{
  "network_scan_id": "net_550e8400",
  "network": "192.168.1.0/24",
  "total_hosts": 254,
  "alive_hosts": 15,
  "scanned_hosts": 15,
  "summary": {
    "web_servers": 8,
    "ssh_servers": 12,
    "database_servers": 3,
    "total_open_ports": 87
  },
  "hosts": [
    {
      "ip": "192.168.1.1",
      "hostname": "router.local",
      "open_ports": [80, 443, 22],
      "services": ["http", "https", "ssh"]
    }
  ]
}
```

### 5. get_scan_status - 查询扫描状态

获取正在进行的扫描任务状态。

**参数**：
- `scan_id` (string, required): 扫描ID

**示例**：

```json
{
  "scan_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**返回结果**：

```json
{
  "scan_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "running",
  "progress": {
    "current_phase": "http_detection",
    "phases_completed": ["port_scan"],
    "percentage": 65,
    "open_ports_found": 5,
    "http_services_found": 2
  },
  "elapsed_time": 30.5,
  "estimated_time_remaining": 15.2
}
```

### 6. get_scan_result - 获取详细结果

获取已完成扫描的详细结果。

**参数**：
- `scan_id` (string, required): 扫描ID
- `include_raw_data` (bool, optional): 是否包含原始数据，默认false

**示例**：

```json
{
  "scan_id": "550e8400-e29b-41d4-a716-446655440000",
  "include_raw_data": false
}
```

### 7. list_active_scans - 列出活跃扫描

获取所有正在进行的扫描任务列表。

**参数**：无

**示例**：

```json
{}
```

**返回结果**：

```json
{
  "active_scans": [
    {
      "scan_id": "scan_001",
      "target": "192.168.1.100",
      "status": "running",
      "start_time": "2024-01-10T10:30:00Z",
      "elapsed_time": 45.2
    },
    {
      "scan_id": "scan_002",
      "target": "10.0.0.0/24",
      "status": "running",
      "type": "network_scan",
      "progress": 65
    }
  ],
  "total_active": 2
}
```

## 配置参数详解

### ScanConfig 对象

```json
{
  // 智能扫描配置
  "smart_scan_enabled": true,        // 是否启用智能扫描
  "smart_scan_threshold": 3,         // 端口阈值，少于此值执行全端口扫描
  
  // RustScan配置
  "rustscan_timeout": 500,           // 超时时间(ms)
  "rustscan_batch_size": 65535,      // 批处理大小
  "rustscan_ports": "21-1000",       // 扫描端口范围
  "rustscan_tries": 1,               // 重试次数
  
  // Banner获取配置
  "banner_timeout": 5.0,             // Banner获取超时(秒)
  "banner_max_bytes": 1024,          // Banner最大字节数
  
  // HTTP探测配置
  "http_timeout": 10.0,              // HTTP请求超时(秒)
  "http_max_redirects": 3,           // 最大重定向次数
  "http_user_agent": "Mozilla/5.0",  // User-Agent
  
  // 目录扫描配置
  "admin_scan_enabled": true,        // 是否启用管理目录扫描
  "admin_scan_threads": 10,          // 并发线程数
  "admin_scan_timeout": 5.0,         // 目录扫描超时(秒)
  
  // 通用配置
  "max_concurrent_targets": 5,       // 最大并发扫描目标数
  "enable_logging": true,            // 是否启用日志
  "log_level": "INFO"               // 日志级别
}
```

## 扫描层级说明

### port_scan - 端口扫描层
- 使用RustScan进行快速端口发现
- 获取开放端口的Banner信息
- 智能决策是否需要全端口扫描

### http_detection - HTTP检测层
- 基于Banner的智能HTTP服务识别
- 自动尝试HTTP/HTTPS协议
- 提取服务器信息、标题、响应头

### web_probe - Web深度探测层
- 扫描常见管理界面路径
- 基于技术栈的智能路径选择
- 识别管理后台、API端点等

## 错误代码

| 错误码 | 说明 | 处理建议 |
|--------|------|----------|
| ERR_INVALID_IP | 无效的IP地址 | 检查IP格式 |
| ERR_SCAN_TIMEOUT | 扫描超时 | 增加超时时间或减少扫描范围 |
| ERR_RUSTSCAN_FAILED | RustScan执行失败 | 检查RustScan是否安装 |
| ERR_NETWORK_UNREACHABLE | 网络不可达 | 检查网络连接 |
| ERR_SCAN_NOT_FOUND | 扫描ID不存在 | 确认扫描ID正确 |
| ERR_MAX_CONCURRENT | 达到最大并发限制 | 等待其他扫描完成 |

## 使用建议

### 1. 智能扫描模式（推荐）
不指定端口，让系统自动决策：
```json
{
  "ip": "目标IP"
}
```

### 2. 快速概览
只需要了解端口开放情况：
```json
{
  "ip": "目标IP",
  "scan_layers": ["port_scan"]
}
```

### 3. Web服务发现
重点关注Web服务：
```json
{
  "ip": "目标IP",
  "ports": [80, 443, 8080, 8443, 3000, 5000, 8000, 9000]
}
```

### 4. 批量扫描优化
大量目标时的配置：
```json
{
  "targets": ["IP1", "IP2", "..."],
  "max_concurrent": 3,
  "config": {
    "rustscan_timeout": 300,
    "smart_scan_threshold": 5
  }
}
```

## 性能指标

| 扫描类型 | 典型耗时 | 说明 |
|---------|---------|------|
| 快速扫描（1-1000端口） | 5-10秒 | 仅端口扫描 |
| 智能扫描（少端口） | 30-60秒 | 包含全端口扫描 |
| 智能扫描（多端口） | 15-30秒 | 跳过全端口扫描 |
| 完整扫描（含Web探测） | 45-120秒 | 所有层级 |
| C段扫描（/24） | 5-15分钟 | 取决于活跃主机数 |

---

更多信息请参考开发文档。 