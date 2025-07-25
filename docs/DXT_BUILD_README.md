# MCP Port Scanner DXT 扩展构建指南

## 概述

DXT (Desktop Extensions) 是 Anthropic 推出的一种新的打包格式，专门用于分发本地 MCP 服务器。通过 DXT，可以将包含多个依赖的 MCP 服务器打包成一个单独的 `.dxt` 文件，用户只需在 Claude Desktop 中单击即可安装。

## 为什么使用 DXT？

1. **解决依赖问题**：自动打包所有 Python 依赖和二进制文件
2. **跨平台支持**：一个包支持 Windows、macOS 和 Linux
3. **简单安装**：用户单击即可安装，无需手动配置
4. **自动更新**：支持版本管理和自动更新
5. **用户友好**：提供配置界面，用户可以轻松设置参数

## DXT 包结构

```
mcp-port-scanner-0.1.1.dxt (ZIP文件)
├── manifest.json                 # 扩展元数据和配置
├── server/                       # 服务器文件
│   ├── src/                      # Python源代码
│   │   └── mcp_port_scanner/     # 项目源代码
│   ├── lib/                      # 打包的Python依赖
│   │   ├── mcp/                  # MCP协议库
│   │   ├── pydantic/             # 数据验证库
│   │   └── ...                   # 其他依赖
│   ├── bin/                      # RustScan二进制文件
│   │   ├── rustscan-windows-x64.exe
│   │   ├── rustscan-macos-arm64
│   │   ├── rustscan-macos-x64
│   │   └── rustscan-linux-x64
│   └── config/                   # 配置文件
│       └── default.toml
```

## 构建步骤

### 1. 安装 DXT CLI 工具

```bash
npm install -g @anthropic-ai/dxt
```

### 2. 构建 DXT 包

#### 方法一：使用构建脚本（推荐）

**Linux/macOS:**
```bash
chmod +x scripts/build-dxt.sh
./scripts/build-dxt.sh
```

**Windows:**
```batch
scripts\build-dxt.bat
```

#### 方法二：使用 Python 脚本

```bash
python scripts/build-dxt.py
```

#### 方法三：使用 DXT CLI 手动构建

```bash
# 验证 manifest.json
dxt validate manifest.json

# 手动准备文件结构后打包
dxt pack . mcp-port-scanner-0.1.1.dxt
```

### 3. 验证构建结果

```bash
# 查看扩展信息
dxt info mcp-port-scanner-0.1.1.dxt

# （可选）为开发测试创建自签名
dxt sign mcp-port-scanner-0.1.1.dxt --self-signed

# 验证签名
dxt verify mcp-port-scanner-0.1.1.dxt
```

## 安装和使用

### 在 Claude Desktop 中安装

1. 打开 Claude Desktop（Windows 或 macOS）
2. 双击 `mcp-port-scanner-0.1.1.dxt` 文件
3. 在弹出的安装对话框中配置参数（可选）
4. 点击"安装"

### 配置选项

安装时可以配置以下选项：

- **日志级别**：DEBUG, INFO, WARNING, ERROR
- **日志文件路径**：保存日志的位置
- **详细日志**：是否输出详细调试信息
- **扫描结果目录**：保存扫描结果的目录
- **最大并发扫描数**：1-20

## 技术细节

### 依赖处理

1. **Python 依赖**：使用 pip 安装到 `server/lib/` 目录
2. **二进制文件**：RustScan 预编译版本放在 `server/bin/`
3. **环境变量**：通过 `PYTHONPATH` 和 `RUSTSCAN_PATH` 配置

### 平台兼容性

- **Python**：要求 3.8 或更高版本
- **操作系统**：Windows、macOS（Intel/ARM）、Linux
- **Claude Desktop**：0.10.0 或更高版本

### 安全考虑

1. 扩展在本地沙箱环境中运行
2. 用户需要明确授权网络访问
3. 敏感配置（如 API 密钥）使用安全输入

## 常见问题

### Q: 构建失败，提示找不到依赖？

A: 确保在虚拟环境外运行构建脚本，脚本会自动处理依赖安装。

### Q: Windows 上 RustScan 无法运行？

A: 检查 Windows Defender 是否阻止了 rustscan-windows-x64.exe。

### Q: 如何更新扩展版本？

A: 修改 manifest.json 中的 version 字段，重新构建即可。

### Q: 扩展太大怎么办？

A: 可以通过 .dxtignore 文件排除不必要的文件，或者使用更激进的依赖清理。

## 发布到 MCP 商店

1. 确保扩展经过充分测试
2. 使用生产证书签名（而非自签名）
3. 提供详细的文档和示例
4. 遵循 MCP 商店的提交指南

## 参考资源

- [DXT 官方文档](https://github.com/anthropics/dxt)
- [MCP 协议规范](https://modelcontextprotocol.io)
- [项目主页](https://github.com/relaxcloud-cn/mcp-port-scanner) 

## 附录：DXT扩展签名完整指南

### 什么是数字签名？

数字签名是一种加密技术，用于验证文件的完整性和来源可信度：

1. **身份验证**：确认文件确实来自声称的发布者
2. **完整性验证**：确保文件没有被篡改
3. **不可否认性**：发布者无法否认签名的文件

### 签名类型

#### 开发测试签名（自签名）
```bash
# 仅用于开发和本地测试
dxt sign mcp-port-scanner-0.1.1.dxt --self-signed
```

#### 生产发布签名（证书签名）
```bash
# 使用正式证书签名
dxt sign mcp-port-scanner-0.1.1.dxt --certificate cert.p12 --password "password"
```

### 获取代码签名证书

#### 推荐证书提供商
1. **DigiCert** - 业界标准（$400-600/年）
2. **Sectigo** - 性价比高（$200-400/年）
3. **GlobalSign** - 国际认可（$300-500/年）
4. **SSL.com** - 价格适中（$150-300/年）

#### 申请材料准备
**个人开发者：**
- 身份证明文件
- 地址证明
- 电话验证

**企业开发者：**
- 营业执照
- 企业验证文件
- 授权人身份证明

### 签名操作步骤

#### 1. 生成证书签名请求(CSR)
```bash
openssl req -new -newkey rsa:2048 -nodes -keyout private.key -out certificate.csr
```

#### 2. 获得证书后安装
```bash
# Windows：双击.p12文件安装
# macOS：添加到钥匙串
# Linux：使用openssl转换
```

#### 3. 正式签名
```bash
# 使用证书文件
dxt sign mcp-port-scanner-0.1.1.dxt \
  --certificate /path/to/cert.p12 \
  --password "cert-password" \
  --timestamp-url "http://timestamp.digicert.com"

# Windows系统证书存储
dxt sign mcp-port-scanner-0.1.1.dxt --thumbprint "证书指纹"

# macOS钥匙串
dxt sign mcp-port-scanner-0.1.1.dxt --identity "Developer ID Application: Your Name"
```

#### 4. 验证签名
```bash
# 验证签名有效性
dxt verify mcp-port-scanner-0.1.1.dxt

# 查看详细信息
dxt info mcp-port-scanner-0.1.1.dxt
```

### 时间戳服务

为确保签名长期有效，建议使用时间戳服务：

```bash
# 常用时间戳服务器
--timestamp-url "http://timestamp.digicert.com"
--timestamp-url "http://time.certum.pl"
--timestamp-url "http://timestamp.comodoca.com"
```

### 签名验证检查清单

- [ ] 证书有效期内
- [ ] 证书链完整
- [ ] 时间戳正确
- [ ] 跨平台验证通过
- [ ] 在Claude Desktop中安装无警告

### 常见签名问题

**Q: 签名后仍显示"未签名"？**
A: 检查证书是否正确安装，时间戳是否添加

**Q: 不同平台签名验证失败？**
A: 确保使用了跨平台兼容的证书格式

**Q: 证书过期怎么办？**
A: 重新申请证书并重新签名，时间戳可保证旧签名有效

**Q: 企业环境要求特定证书？**
A: 联系IT部门获取企业认可的证书颁发机构列表 