# MCP Port Scanner 变更日志

## [0.1.1] - 2025-01-15

### 🚀 重大改进：内置 RustScan 支持

#### ✨ 新增功能

1. **RustScan 二进制文件管理**
   - 新增 `RustScanManager` 类，智能管理跨平台 RustScan 二进制文件
   - 支持自动检测和使用本地 `bin/` 目录中的 RustScan
   - 回退机制：优先使用本地版本，其次使用系统安装版本

2. **自动下载脚本**
   - 新增 `scripts/download_rustscan.py`，支持自动下载对应平台的 RustScan
   - 支持的平台：Windows x64, Linux x64, macOS x64, macOS ARM64
   - 智能平台检测和版本验证

3. **一键安装脚本**
   - 新增 `scripts/setup.sh`，提供完整的一键安装体验
   - 自动检查 Python 版本、安装依赖、下载 RustScan
   - 完整的错误处理和用户指导

4. **CLI 增强**
   - 新增 `rustscan` 命令，检查 RustScan 安装状态
   - 提供详细的安装建议和故障排除信息
   - 更友好的错误提示和安装指导

5. **项目配置完善**
   - 新增 `setup.py` 支持标准 Python 包安装
   - 新增 `requirements.txt` 规范依赖管理
   - 新增 `INSTALL.md` 详细安装指南

#### 🛠️ 技术改进

1. **无缝集成**
   - 修改 `PortScanner` 类，使用 `RustScanManager` 构建命令
   - 消除硬编码的 "rustscan" 命令调用
   - 自动路径解析和错误处理

2. **跨平台兼容**
   - 支持 Windows, Linux, macOS 全平台
   - 智能二进制文件选择和权限处理
   - 统一的命令构建接口

3. **错误处理优化**
   - 详细的安装状态检查
   - 友好的错误信息和解决建议
   - 渐进式回退机制

#### 📖 文档更新

1. **README.md**
   - 更新安装说明，推荐一键安装
   - 新增 RustScan 状态检查命令说明
   - 完善 CLI 使用示例

2. **新增文档**
   - `INSTALL.md`：详细安装指南
   - `bin/README.md`：二进制文件说明
   - `CHANGELOG.md`：变更记录

#### 🎯 用户体验提升

**之前：**
```bash
# 用户需要手动安装 RustScan
brew install rustscan  # macOS
sudo apt install rustscan  # Linux
# Windows 用户需要复杂的手动安装
```

**现在：**
```bash
# 一键安装，包含 RustScan
bash scripts/setup.sh

# 或者手动下载
python scripts/download_rustscan.py

# 检查状态
python -m mcp_port_scanner.interfaces.cli_interface rustscan
```

#### 🔧 开发者体验

1. **简化部署**
   - 项目自包含，无需外部依赖下载
   - Docker 镜像体积减小
   - 分发更简单

2. **调试增强**
   - 详细的 RustScan 路径和版本信息
   - 清晰的错误诊断
   - 完整的安装状态报告

#### 📊 兼容性

- ✅ 向后兼容：现有功能完全保持
- ✅ 配置兼容：所有扫描参数和配置不变
- ✅ 接口兼容：MCP 工具接口无变化
- ✅ Docker 兼容：Docker 环境正常工作

#### 🎉 总结

这次更新显著提升了用户体验，将复杂的 RustScan 安装过程简化为一键操作，同时保持了项目的灵活性和兼容性。用户现在可以：

1. **零配置开始**：克隆项目后一键安装即可使用
2. **跨平台支持**：Windows、Linux、macOS 统一体验
3. **智能管理**：自动检测和管理 RustScan 版本
4. **简化分发**：项目自包含，易于部署和分享

这一改进实现了您的目标：**将 RustScan 直接作为程序的一部分对外发布，无需用户手动下载安装**。

---

## [0.1.0] - 2025-01-08

### 初始版本
- 基于 MCP 协议的智能端口扫描器
- 三层扫描架构：端口发现 → HTTP检测 → Web探测
- 支持 CLI、MCP、Python SDK 多种接口
- Docker 容器化支持 