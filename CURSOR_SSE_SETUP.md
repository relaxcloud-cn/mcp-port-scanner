# 🔥 Cursor SSE模式配置指南

## 🎯 概述

Cursor SSE模式是专门为Cursor编辑器优化的实时端口扫描接口，提供0.5秒更新频率的高性能SSE流式传输。

## 🚀 快速启动

### 1. **启动Cursor SSE服务器**

```bash
# 启动Cursor优化的SSE服务器
PYTHONPATH=src python -m mcp_port_scanner.cli server --mode cursor --port 8080
```

### 2. **配置Cursor MCP**

编辑Cursor的MCP配置文件：

**macOS/Linux**: `~/.cursor/mcp_settings.json`
**Windows**: `%APPDATA%\Cursor\mcp_settings.json`

```json
{
  "mcpServers": {
    "port-scanner": {
      "command": "python",
      "args": [
        "-m", 
        "mcp_port_scanner.cli",
        "server",
        "--mode", "cursor",
        "--host", "127.0.0.1",
        "--port", "8080"
      ],
      "cwd": "/Users/sky/Prism/mcp-port-scanner",
      "env": {
        "PYTHONPATH": "src"
      }
    }
  }
}
```

> **重要**: 将 `cwd` 路径替换为您的实际项目路径！

## 🌟 Cursor SSE特性

### **🔥 实时特性**
- ✅ **0.5秒更新频率** - 比标准HTTP模式快2倍
- ✅ **智能事件推送** - 仅在有变化时推送
- ✅ **渐进式结果** - 每发现一个端口立即通知
- ✅ **优化数据格式** - 专为Cursor界面设计

### **📊 SSE事件类型**
| 事件类型 | 触发时机 | 数据内容 |
|---------|----------|----------|
| `start` | 扫描开始 | scan_id, target |
| `status` | 状态变化 | status, scan_id |
| `progress` | 发现新端口/服务 | ports, http, admin计数 |
| `complete` | 扫描完成 | 完整结果摘要 |
| `error` | 扫描失败 | 错误信息 |

## 📚 使用示例

### **1. 启动实时扫描**

在Cursor中执行：

```javascript
// POST /cursor/scan
{
  "ip": "8.8.8.8",
  "real_time": true,
  "scan_layers": ["port_scan", "http_detection", "web_probe"]
}
```

响应：
```json
{
  "scan_id": "abc123",
  "status": "started",
  "target": "8.8.8.8",
  "stream_url": "/cursor/scan/abc123/stream",
  "cursor_compatible": true
}
```

### **2. 订阅SSE进度流**

```javascript
// GET /cursor/scan/{scan_id}/stream
const eventSource = new EventSource('/cursor/scan/abc123/stream');

eventSource.onmessage = function(event) {
  const data = JSON.parse(event.data);
  
  switch(data.type) {
    case 'start':
      console.log(`🚀 开始扫描: ${data.data.target}`);
      break;
      
    case 'progress':
      console.log(`📊 进度更新: ${data.data.open_ports} 端口, ${data.data.new_ports} 新发现`);
      break;
      
    case 'complete':
      console.log(`✅ 扫描完成: ${data.data.summary.total_ports} 端口`);
      eventSource.close();
      break;
  }
};
```

### **3. 实时事件示例**

```json
// 开始事件
{
  "type": "start",
  "timestamp": "2025-01-10T04:33:00Z",
  "data": {
    "scan_id": "abc123",
    "target": "8.8.8.8"
  }
}

// 进度事件
{
  "type": "progress", 
  "timestamp": "2025-01-10T04:33:02Z",
  "data": {
    "scan_id": "abc123",
    "open_ports": 2,
    "http_services": 1,
    "admin_interfaces": 0,
    "new_ports": 1,
    "new_http": 1,
    "new_admin": 0
  }
}

// 完成事件
{
  "type": "complete",
  "timestamp": "2025-01-10T04:33:15Z", 
  "data": {
    "scan_id": "abc123",
    "target": "8.8.8.8",
    "summary": {
      "total_ports": 3,
      "http_services": 2,
      "admin_interfaces": 1,
      "scan_duration": 12.5
    },
    "open_ports": [
      {"port": 80, "service": "http", "version": "nginx/1.18"},
      {"port": 443, "service": "https", "version": "nginx/1.18"},
      {"port": 8080, "service": "http-proxy", "version": null}
    ],
    "admin_interfaces": [
      {"path": "/admin", "title": "Admin Panel", "status": 200}
    ]
  }
}
```

## 🛠️ 高级配置

### **性能优化**

```json
{
  "ip": "target.com",
  "config": {
    "rustscan_timeout": 1000,
    "banner_timeout": 3.0,
    "http_timeout": 5.0,
    "smart_scan_threshold": 3
  },
  "scan_layers": ["port_scan", "http_detection"],
  "real_time": true
}
```

### **批量扫描支持**

虽然是实时接口，仍可以快速启动多个扫描：

```bash
# 同时启动3个扫描
curl -X POST http://127.0.0.1:8080/cursor/scan -d '{"ip":"8.8.8.8"}'
curl -X POST http://127.0.0.1:8080/cursor/scan -d '{"ip":"1.1.1.1"}'
curl -X POST http://127.0.0.1:8080/cursor/scan -d '{"ip":"github.com"}'
```

## 🔧 故障排除

### **常见问题**

1. **SSE连接断开**
   - 检查网络稳定性
   - 确认端口8080未被占用
   - 重启Cursor SSE服务器

2. **事件延迟**
   - 确认使用cursor模式而非http模式
   - 检查系统负载
   - 减少并发扫描数量

3. **数据格式错误**
   - 确认使用 `/cursor/scan` 端点
   - 检查JSON格式正确性
   - 验证scan_id有效性

### **调试命令**

```bash
# 测试Cursor SSE服务器
curl http://127.0.0.1:8080/

# 测试扫描启动
curl -X POST http://127.0.0.1:8080/cursor/scan \
  -H "Content-Type: application/json" \
  -d '{"ip": "8.8.8.8", "real_time": true}'

# 测试SSE流 (在浏览器中打开)
http://127.0.0.1:8080/cursor/scan/{scan_id}/stream
```

## 🎯 与其他模式对比

| 特性 | Cursor SSE | 标准HTTP | MCP stdio |
|------|------------|----------|-----------|
| **实时性** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ |
| **更新频率** | 0.5秒 | 1秒 | 完成后 |
| **Cursor兼容** | ✅ 优化 | ✅ 基础 | ✅ 原生 |
| **事件粒度** | 渐进式 | 批量 | 最终 |
| **资源消耗** | 中等 | 中等 | 低 |

## 🌟 最佳实践

### **推荐配置**
- ✅ 使用 `cursor` 模式获得最佳体验
- ✅ 设置合理的超时时间避免卡顿
- ✅ 监听所有SSE事件类型
- ✅ 实现适当的错误处理

### **性能建议**
- 🔥 单次扫描：使用实时SSE流
- 🔥 批量扫描：启动多个独立扫描
- 🔥 大型网络：分批扫描，避免过载

---

## 🎉 完成

Cursor SSE模式现已配置完成！您将获得：

**核心优势**：
- ⚡ 实时进度反馈
- 🎯 Cursor界面优化
- 📊 渐进式结果展示
- 🔥 高性能SSE传输
- 🛠️ 智能事件推送

享受实时端口扫描的极致体验！ 🚀 