# MCP Port Scanner 安装指南

本文档提供详细的安装和配置说明。

## 🚀 快速安装

### 方法1: 一键安装脚本（推荐）

```bash
# 克隆项目
git clone https://github.com/relaxcloud-cn/mcp-port-scanner.git
cd mcp-port-scanner

# 运行一键安装脚本
bash scripts/setup.sh
```

### 方法2: 手动安装

```bash
# 1. 安装 Python 依赖
pip install -r requirements.txt

# 2. 下载 RustScan
python scripts/download_rustscan.py

# 3. 验证安装
python -m mcp_port_scanner.interfaces.cli_interface rustscan
```

## 📋 系统要求

- **Python**: 3.8 或更高版本
- **操作系统**: Windows 10+, Linux, macOS
- **内存**: 建议 2GB+ 
- **网络**: 需要互联网连接（用于下载 RustScan）

## 🔧 RustScan 安装

项目会自动将 RustScan 下载到 `bin/` 目录，无需用户手动安装。

### 支持的平台

| 平台 | 文件名 | 状态 |
|------|--------|------|
| Windows x64 | `rustscan-windows-x64.exe` | ✅ 支持 |
| Linux x64 | `rustscan-linux-x64` | ✅ 支持 |
| macOS x64 | `rustscan-macos-x64` | ✅ 支持 |
| macOS ARM64 | `rustscan-macos-arm64` | ✅ 支持 |

### 手动下载 RustScan

如果自动下载失败，可以手动下载：

1. 访问 [RustScan 发布页面](https://github.com/RustScan/RustScan/releases/tag/2.0.1)
2. 下载对应平台的文件
3. 重命名并放置到 `bin/` 目录
4. 设置执行权限（Linux/macOS）：`chmod +x bin/rustscan-*`

## 🐳 Docker 安装

```bash
# 构建镜像
docker-compose build

# 启动服务
docker-compose up -d mcp-port-scanner

# 验证运行
docker-compose ps
```

## 🔍 验证安装

```bash
# 检查 RustScan 状态
python -m mcp_port_scanner.interfaces.cli_interface rustscan

# 测试扫描
python -m mcp_port_scanner.interfaces.cli_interface scan 8.8.8.8

# 查看帮助
python -m mcp_port_scanner.interfaces.cli_interface --help
```

期望输出：
```
🔍 RustScan 安装状态检查
==================================================
🖥️  平台: linux-x64
📁 二进制目录: /path/to/mcp-port-scanner/bin

✅ 本地安装: /path/to/mcp-port-scanner/bin/rustscan-linux-x64
❌ 系统安装: 未找到

🎯 当前使用: /path/to/mcp-port-scanner/bin/rustscan-linux-x64
✅ 验证状态: RustScan 2.0.1

🎉 RustScan 已正确安装并可用！
```

## 🎯 MCP 配置

### Cursor 配置

在 Cursor 设置中添加以下 MCP 配置：

```json
{
  "mcpServers": {
    "port-scanner-local": {
      "command": "python",
      "args": ["-m", "mcp_port_scanner.interfaces.mcp_local_server"],
      "cwd": "/path/to/mcp-port-scanner",
      "env": {
        "PYTHONPATH": "src"
      },
      "description": "MCP智能端口扫描器"
    }
  }
}
```

### Docker MCP 配置

```json
{
  "mcpServers": {
    "port-scanner-docker": {
      "command": "docker",
      "args": ["exec", "-i", "mcp-port-scanner", "python", "-m", "mcp_port_scanner.interfaces.mcp_local_server"],
      "description": "Docker版MCP端口扫描器"
    }
  }
}
```

## 🛠️ 开发环境配置

```bash
# 克隆项目
git clone https://github.com/relaxcloud-cn/mcp-port-scanner.git
cd mcp-port-scanner

# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装开发依赖
pip install -r requirements.txt
pip install -e .

# 下载 RustScan
python scripts/download_rustscan.py

# 运行测试
python -m pytest tests/
```

## ❓ 常见问题

### Q: RustScan 下载失败怎么办？

A: 可以尝试以下方法：
1. 检查网络连接
2. 手动下载并放置到 `bin/` 目录
3. 使用系统包管理器安装 RustScan
4. 使用 Docker 环境

### Q: 权限错误怎么解决？

A: Linux/macOS 用户需要设置执行权限：
```bash
chmod +x bin/rustscan-*
```

### Q: Python 版本太低怎么办？

A: 需要升级到 Python 3.8+：
```bash
# Ubuntu/Debian
sudo apt update && sudo apt install python3.8

# macOS
brew install python@3.8

# Windows
# 访问 python.org 下载最新版本
```

### Q: 如何在企业网络中使用？

A: 可能需要配置代理：
```bash
export HTTP_PROXY=http://proxy.company.com:8080
export HTTPS_PROXY=http://proxy.company.com:8080
python scripts/download_rustscan.py
```

## 📞 获取帮助

- 📖 查看文档：`docs/` 目录
- 🐛 报告问题：GitHub Issues
- 💬 讨论交流：GitHub Discussions

## 🔄 更新

```bash
# 更新代码
git pull origin master

# 更新依赖
pip install -r requirements.txt --upgrade

# 更新 RustScan
python scripts/download_rustscan.py --force
``` 