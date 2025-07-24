# 二进制文件目录

此目录包含项目所需的二进制依赖文件，确保跨平台兼容性。

## RustScan 二进制文件

### 支持的平台
- Windows (x64): `rustscan-windows-x64.exe`
- Linux (x64): `rustscan-linux-x64`
- macOS (x64): `rustscan-macos-x64`
- macOS (ARM64): `rustscan-macos-arm64`

### 自动下载
运行以下命令自动下载所需平台的 RustScan：

```bash
# 下载当前平台
python scripts/download_rustscan.py

# 下载所有平台（用于发布）
python scripts/download_rustscan.py --all
```

### 手动下载
如果自动下载失败，请手动下载并放置到对应位置：

1. 访问 RustScan 发布页面：https://github.com/RustScan/RustScan/releases
2. 下载对应平台的二进制文件
3. 重命名并放置到此目录

### 版本信息
- RustScan 版本：2.0.1
- 更新日期：2025-01-15 