# 🎯 Cursor MCP配置指南

## 📋 概述

本指南将帮您在Cursor中配置MCP端口扫描器，实现智能端口扫描功能的无缝集成。

## 🚀 快速配置

### 1. **启动MCP服务器**

在项目目录下启动标准MCP服务器：

```bash
# 方式1：标准MCP协议 (推荐用于Cursor)
PYTHONPATH=src python -m mcp_port_scanner.cli server --mode mcp

# 方式2：HTTP/SSE接口 (用于Web集成)
PYTHONPATH=src python -m mcp_port_scanner.cli server --mode http --port 8080
```

### 2. **配置Cursor MCP**

创建或编辑Cursor的MCP配置文件：

**macOS/Linux**: `~/.cursor/mcp_settings.json`
**Windows**: `%APPDATA%\Cursor\mcp_settings.json`

添加以下配置：

```json
{
  "mcpServers": {
    "port-scanner": {
      "command": "python",
      "args": [
        "-m", 
        "mcp_port_scanner.mcp_server"
      ],
      "cwd": "/Users/sky/Prism/mcp-port-scanner",
      "env": {
        "PYTHONPATH": "src"
      }
    }
  }
}
```

> **注意**: 将 `cwd` 路径替换为您的实际项目路径！

### 3. **Docker方式配置** (原有配置)

如果您使用Docker，现有的 `mcp.json` 配置已可用：

```json
{
  "mcpServers": {
    "port-scanner": {
      "command": "docker",
      "args": [
        "compose", 
        "exec", 
        "-T",
        "mcp-port-scanner", 
        "python", 
        "-m", 
        "mcp_port_scanner.mcp_server"
      ],
      "cwd": "/Users/sky/Prism/mcp-port-scanner"
    }
  }
}
```

## 🛠️ 详细配置选项

### **MCP服务器模式**

| 模式 | 命令 | 用途 | Cursor兼容 |
|------|------|------|------------|
| **stdio** | `--mode mcp` | 标准MCP协议 | ✅ 完全兼容 |
| **http** | `--mode http` | HTTP/SSE接口 | ❌ 需要代理 |

### **配置参数**

```json
{
  "mcpServers": {
    "port-scanner": {
      "command": "python",
      "args": ["-m", "mcp_port_scanner.mcp_server"],
      "cwd": "/path/to/mcp-port-scanner",
      "env": {
        "PYTHONPATH": "src",
        "LOG_LEVEL": "INFO",
        "RUSTSCAN_TIMEOUT": "3000",
        "HTTP_TIMEOUT": "10.0"
      },
      "timeout": 30000
    }
  }
}
```

## 📚 使用示例

配置完成后，在Cursor中可以使用以下MCP工具：

### **1. 智能扫描单个IP**
```json
{
  "tool": "scan_target",
  "arguments": {
    "ip": "8.8.8.8",
    "scan_layers": ["port_scan", "http_detection", "web_probe"]
  }
}
```

### **2. 批量扫描多个目标**
```json
{
  "tool": "batch_scan", 
  "arguments": {
    "targets": [
      {"ip": "8.8.8.8"},
      {"ip": "1.1.1.1"},
      {"ip": "github.com"}
    ],
    "max_concurrent": 3
  }
}
```

### **3. 快速端口扫描**
```json
{
  "tool": "quick_scan",
  "arguments": {
    "ip": "scanme.nmap.org"
  }
}
```

### **4. 网络段扫描**
```json
{
  "tool": "scan_network",
  "arguments": {
    "network": "192.168.1.0/24",
    "max_concurrent": 10
  }
}
```

## 🔧 故障排除

### **常见问题**

1. **"工具不可用"错误**
   - 确认MCP服务器正在运行
   - 检查路径配置是否正确
   - 验证PYTHONPATH设置

2. **扫描速度慢**
   - 调整 `rustscan_timeout` 配置
   - 减少并发数量
   - 使用 `quick_scan` 仅扫描端口

3. **权限问题**
   - 确保有网络访问权限
   - 检查防火墙设置
   - 在某些系统上可能需要sudo权限

### **调试命令**

```bash
# 测试MCP服务器
PYTHONPATH=src python -c "
from mcp_port_scanner.mcp_server import list_tools
import asyncio
asyncio.run(list_tools())
"

# 测试单次扫描
PYTHONPATH=src python -c "
from mcp_port_scanner.service import scan
result = scan('8.8.8.8')
print(f'发现 {len(result.open_ports)} 个开放端口')
"
```

## 🌟 高级功能

### **实时进度监控** (HTTP模式)

```bash
# 启动HTTP/SSE服务器
PYTHONPATH=src python -m mcp_port_scanner.cli server --mode http --port 8080

# 在浏览器中访问实时监控
# http://127.0.0.1:8080/scan/{scan_id}/stream
```

### **配置优化**

```json
{
  "config": {
    "rustscan_timeout": 1000,
    "banner_timeout": 3.0,
    "http_timeout": 5.0,
    "admin_scan_enabled": true,
    "admin_scan_threads": 20,
    "smart_scan_threshold": 3
  }
}
```

## 📞 支持

如果遇到问题：

1. 查看日志文件：`logs/mcp_server_*.log`
2. 检查配置文件语法
3. 验证网络连接
4. 确认所有依赖已安装

---

## 🎉 完成

配置完成后，您可以在Cursor中直接使用智能端口扫描功能！

**核心优势**：
- ✅ 保持现有MCP架构不变
- ✅ 智能扫描策略自动优化
- ✅ 实时进度反馈
- ✅ 支持批量和网络段扫描
- ✅ 完全兼容Cursor MCP协议 