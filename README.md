# 🚀 MCP智能端口扫描器

<div align="center">

[![Python Version](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![MCP Protocol](https://img.shields.io/badge/MCP-Compatible-green.svg)](https://modelcontextprotocol.org/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

基于MCP协议的智能分层端口扫描服务，专为AI助手和开发工具设计

[快速开始](#-快速开始) • [功能特性](#-功能特性) • [文档](#-文档) • [演示](#-演示)

</div>

## 🌟 项目亮点

- **🧠 智能扫描**：根据端口数量动态调整扫描深度，平衡效率与覆盖率
- **🎯 分层递进**：端口扫描 → HTTP检测 → Web深度探测，逐层深入
- **⚡ 极速性能**：基于RustScan，比传统扫描器快10倍
- **🔌 多接口支持**：MCP协议、HTTP/SSE、Cursor优化接口
- **📊 实时反馈**：SSE推送进度，让扫描过程可视化

## 🎯 适用场景

- **安全审计**：快速发现网络资产和潜在风险
- **运维监控**：定期扫描基础设施，确保服务正常
- **开发测试**：验证端口配置和服务部署
- **AI集成**：通过MCP协议与Cursor等AI工具无缝集成

## 🚀 快速开始

### 1. 安装

```bash
# 克隆项目
git clone https://github.com/yourusername/mcp-port-scanner.git
cd mcp-port-scanner

# 安装依赖
pip install -r requirements.txt
pip install mcp

# 安装RustScan（必需）
# macOS
brew install rustscan

# Linux
wget https://github.com/RustScan/RustScan/releases/download/2.0.1/rustscan_2.0.1_amd64.deb
sudo dpkg -i rustscan_2.0.1_amd64.deb
```

### 2. 快速使用

```bash
# 扫描单个目标
python -m mcp_port_scanner scan 192.168.1.1

# 扫描指定端口
python -m mcp_port_scanner scan 192.168.1.1 -p 80,443,8080

# 批量扫描
python -m mcp_port_scanner batch 192.168.1.1 192.168.1.2 192.168.1.3
```

### 3. Cursor集成

编辑 `~/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "port-scanner": {
      "command": "/path/to/venv/bin/python3",
      "args": ["-m", "mcp_port_scanner.mcp_server"],
      "cwd": "/path/to/mcp-port-scanner"
    }
  }
}
```

重启Cursor后即可使用。

## 📚 功能特性

### 智能扫描模式

```python
# 自动决策扫描深度
if 开放端口数 < 3:
    执行全端口深度扫描  # 可能有隐藏服务
else:
    跳过全端口扫描      # 已获得足够信息
```

### 分层扫描架构

1. **端口扫描层**：RustScan快速发现 + Banner获取
2. **HTTP检测层**：智能识别Web服务，自动尝试HTTP/HTTPS
3. **Web探测层**：扫描管理界面、API端点、敏感目录

### MCP工具集

- `scan_target` - 智能扫描单个IP
- `batch_scan` - 批量扫描多个目标
- `quick_scan` - 快速端口扫描
- `scan_network` - C段网络扫描
- `get_scan_status` - 查询扫描进度
- `get_scan_result` - 获取详细结果

## 📖 文档

- 📘 [快速开始指南](./docs/QUICKSTART.md) - 5分钟上手教程
- 📗 [开发文档](./docs/DEVELOPMENT_GUIDE.md) - 架构设计与扩展开发
- 📙 [API参考](./docs/API_REFERENCE.md) - 详细的API文档和示例
- 📕 [架构设计](./docs/ARCHITECTURE.md) - 深入了解设计理念

## 🔧 使用示例

### Python SDK

```python
from mcp_port_scanner import PortScannerSDK

# 创建实例
sdk = PortScannerSDK()

# 扫描目标
result = sdk.scan("192.168.1.1")
print(f"发现 {len(result.open_ports)} 个开放端口")
print(f"发现 {len(result.http_services)} 个Web服务")
print(f"发现 {len(result.admin_directories)} 个管理界面")
```

### HTTP API

```bash
# 启动HTTP服务
python -m mcp_port_scanner server --mode http --port 8080

# 调用API
curl -X POST http://localhost:8080/scan \
  -H "Content-Type: application/json" \
  -d '{"target": "192.168.1.1"}'
```

### JavaScript集成

```javascript
// 监听实时进度
const eventSource = new EventSource('/scan/xxx/stream');
eventSource.onmessage = (event) => {
  const progress = JSON.parse(event.data);
  console.log(`扫描进度: ${progress.percentage}%`);
};
```

## 🏗️ 架构设计

```
┌─────────────────────────────────────────┐
│          接口层 (Interfaces)             │
├────────┬────────┬────────┬──────────────┤
│  CLI   │  MCP   │  HTTP  │  Cursor SSE  │
├────────┴────────┴────────┴──────────────┤
│         适配器层 (Adapters)              │
├──────────────────────────────────────────┤
│         服务层 (Service Layer)           │
├────────┬────────┬────────┬──────────────┤
│Scanner │Detector│ Prober │    Models    │
└────────┴────────┴────────┴──────────────┘
```

## 🎯 性能指标

| 扫描类型 | 典型耗时 | 说明 |
|---------|---------|------|
| 快速扫描 | 5-10秒 | 仅常用端口 |
| 智能扫描（少端口） | 30-60秒 | 包含全端口扫描 |
| 智能扫描（多端口） | 15-30秒 | 跳过全端口扫描 |
| 完整扫描 | 45-120秒 | 所有扫描层级 |
| C段扫描 | 5-15分钟 | 254个IP地址 |

## 🛡️ 安全说明

- 仅在授权的网络环境中使用
- 遵守当地法律法规
- 合理控制扫描频率
- 不记录敏感信息

## 🤝 贡献指南

我们欢迎并感谢社区的贡献。请参考[贡献指南](./CONTRIBUTING.md)来帮助改进项目。

## 📄 许可证

本项目采用MIT许可证 - 查看 [LICENSE](LICENSE) 文件了解详情

## 🙏 致谢

- [RustScan](https://github.com/RustScan/RustScan) - 超快的端口扫描器
- [MCP](https://modelcontextprotocol.org/) - Model Context Protocol
- [FastAPI](https://fastapi.tiangolo.com/) - 现代Web框架

---

<div align="center">
Made with ❤️ by the MCP Port Scanner Team
</div> 