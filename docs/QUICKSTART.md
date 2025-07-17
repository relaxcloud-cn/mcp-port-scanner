# MCP端口扫描器 - 快速开始指南

## 5分钟快速上手

### 1. 环境准备

```bash
# 克隆项目
git clone https://github.com/yourusername/mcp-port-scanner.git
cd mcp-port-scanner

# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt
pip install mcp  # MCP SDK

# 安装RustScan（必需）
# macOS
brew install rustscan

# Linux
wget https://github.com/RustScan/RustScan/releases/download/2.0.1/rustscan_2.0.1_amd64.deb
sudo dpkg -i rustscan_2.0.1_amd64.deb

# 或使用Docker
docker pull rustscan/rustscan:2.0.0
```

### 2. 快速测试

```bash
# 测试扫描本机
python -m mcp_port_scanner scan 127.0.0.1

# 扫描指定端口
python -m mcp_port_scanner scan 192.168.1.1 -p 80,443,8080

# 批量扫描
python -m mcp_port_scanner batch 192.168.1.1 192.168.1.2 192.168.1.3
```

### 3. 启动MCP服务

```bash
# 标准MCP服务（用于Cursor）
python -m mcp_port_scanner server

# HTTP/SSE服务（用于Web）
python -m mcp_port_scanner server --mode http --port 8080

# Cursor优化SSE服务
python -m mcp_port_scanner server --mode cursor --port 8080
```

## Cursor集成配置

### 1. 配置MCP服务

编辑 `~/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "port-scanner": {
      "command": "/path/to/venv/bin/python3",
      "args": ["-m", "mcp_port_scanner.interfaces.mcp_local_server"],
      "cwd": "/path/to/mcp-port-scanner",
      "env": {
        "PYTHONPATH": "src"
      }
    }
  }
}
```

### 2. 重启Cursor

重启Cursor后，你应该能看到以下工具：
- `scan_target` - 扫描单个IP
- `batch_scan` - 批量扫描
- `quick_scan` - 快速扫描
- `scan_network` - 网段扫描
- `get_scan_status` - 查询状态
- `get_scan_result` - 获取结果

### 3. 在Cursor中使用

```
请扫描 192.168.1.1
```

Cursor会自动调用相应的MCP工具。

## Python SDK使用

### 基础用法

```python
from mcp_port_scanner import PortScannerSDK

# 创建SDK实例
sdk = PortScannerSDK()

# 扫描单个目标
result = sdk.scan("192.168.1.1")
print(f"发现 {len(result.open_ports)} 个开放端口")

# 扫描指定端口
result = sdk.scan("192.168.1.1", ports=[80, 443, 8080])

# 仅端口扫描
result = sdk.scan_ports_only("192.168.1.1")

# 批量扫描
results = sdk.batch_scan(["192.168.1.1", "192.168.1.2"])
```

### 异步用法

```python
import asyncio
from mcp_port_scanner import PortScannerSDK

async def main():
    sdk = PortScannerSDK()
    
    # 异步扫描
    result = await sdk.scan_async("192.168.1.1")
    
    # 带进度回调
    async def on_progress(stage, message):
        print(f"[{stage}] {message}")
    
    result = await sdk.scan_with_progress("192.168.1.1", on_progress)
    
    # 批量异步扫描
    results = await sdk.batch_scan_async(
        ["192.168.1.1", "192.168.1.2"],
        max_concurrent=3
    )

asyncio.run(main())
```

### 自定义配置

```python
from mcp_port_scanner import PortScannerSDK, ScanConfig

# 创建自定义配置
config = ScanConfig(
    smart_scan_enabled=True,      # 启用智能扫描
    smart_scan_threshold=5,       # 端口阈值
    rustscan_timeout=1000,        # 扫描超时
    http_timeout=15.0,            # HTTP超时
    admin_scan_enabled=True       # 启用目录扫描
)

# 使用自定义配置
sdk = PortScannerSDK(config)
result = sdk.scan("192.168.1.1")
```

## HTTP API使用

### 启动HTTP服务

```bash
python -m mcp_port_scanner server --mode http --port 8080
```

### API调用示例

```bash
# 启动扫描
curl -X POST http://localhost:8080/scan \
  -H "Content-Type: application/json" \
  -d '{
    "target": "192.168.1.1",
    "scan_layers": ["port_scan", "http_detection", "web_probe"]
  }'

# 返回
{
  "scan_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "started",
  "stream_url": "/scan/550e8400-e29b-41d4-a716-446655440000/stream"
}

# 获取实时进度（SSE）
curl http://localhost:8080/scan/550e8400-e29b-41d4-a716-446655440000/stream

# 获取结果
curl http://localhost:8080/scan/550e8400-e29b-41d4-a716-446655440000/result
```

### JavaScript客户端示例

```javascript
// 启动扫描
async function startScan(ip) {
  const response = await fetch('http://localhost:8080/scan', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ target: ip })
  });
  
  const { scan_id, stream_url } = await response.json();
  
  // 监听实时进度
  const eventSource = new EventSource(`http://localhost:8080${stream_url}`);
  
  eventSource.onmessage = (event) => {
    const data = JSON.parse(event.data);
    console.log('进度更新:', data);
  };
  
  eventSource.addEventListener('complete', (event) => {
    const result = JSON.parse(event.data);
    console.log('扫描完成:', result);
    eventSource.close();
  });
}

// 使用
startScan('192.168.1.1');
```

## Docker使用

### 使用预构建镜像

```bash
# 拉取镜像
docker pull yourusername/mcp-port-scanner:latest

# 运行MCP服务
docker run -it --rm \
  -v ~/.cursor/mcp.json:/root/.cursor/mcp.json \
  yourusername/mcp-port-scanner

# 运行HTTP服务
docker run -it --rm \
  -p 8080:8080 \
  yourusername/mcp-port-scanner \
  python -m mcp_port_scanner server --mode http --host 0.0.0.0
```

### 构建自己的镜像

```bash
# 构建镜像
docker build -t my-port-scanner .

# 运行扫描
docker run --rm my-port-scanner \
  python -m mcp_port_scanner scan 192.168.1.1
```

## 常见问题

### Q1: RustScan命令未找到

**解决方案**：
```bash
# 检查是否安装
which rustscan

# 如果未安装，请按照环境准备章节安装
# 或使用Docker版本
alias rustscan='docker run -it --rm --name rustscan rustscan/rustscan:2.0.0'
```

### Q2: 扫描速度很慢

**解决方案**：
```python
# 调整配置参数
config = ScanConfig(
    rustscan_timeout=200,        # 减少超时时间
    rustscan_batch_size=65535,   # 增加并发
    smart_scan_threshold=5       # 提高阈值避免全端口扫描
)
```

### Q3: Cursor显示"0 tools enabled"

**解决方案**：
1. 检查Python路径是否正确
2. 确保使用完整路径（不要用别名）
3. 检查日志：`tail -f ~/.cursor/logs/mcp.log`
4. 重启Cursor

### Q4: 内存占用过高

**解决方案**：
```python
# 限制并发数
config = ScanConfig(
    max_concurrent_targets=3,     # 减少并发目标
    admin_scan_threads=5,         # 减少目录扫描线程
    rustscan_batch_size=10000    # 减少批处理大小
)
```

### Q5: 扫描被防火墙拦截

**解决方案**：
1. 降低扫描速度
2. 使用更长的超时时间
3. 减少并发连接数
4. 考虑使用代理或VPN

## 性能调优

### 快速扫描配置

```python
# 适合快速概览
fast_config = ScanConfig(
    rustscan_timeout=200,
    smart_scan_enabled=False,  # 禁用智能扫描
    admin_scan_enabled=False   # 禁用目录扫描
)
```

### 深度扫描配置

```python
# 适合详细扫描
deep_config = ScanConfig(
    rustscan_timeout=3000,
    smart_scan_threshold=1,    # 总是全端口扫描
    admin_scan_enabled=True,
    admin_scan_threads=20
)
```

### 批量扫描优化

```python
# 适合大规模扫描
batch_config = ScanConfig(
    max_concurrent_targets=10,
    rustscan_timeout=500,
    smart_scan_threshold=5
)
```

## 故障排除

### 启用调试日志

```python
config = ScanConfig(
    enable_logging=True,
    log_level="DEBUG"
)
```

### 查看日志文件

```bash
# 查看最新日志
tail -f logs/mcp_server_*.log

# 搜索错误
grep ERROR logs/*.log

# 查看特定IP的扫描日志
grep "192.168.1.1" logs/*.log
```

### 测试连接

```python
# 测试脚本
from mcp_port_scanner import PortScanner
import asyncio

async def test():
    scanner = PortScanner()
    # 测试本地连接
    result = await scanner.scan_target(ScanTarget(ip="127.0.0.1", ports=[22, 80]))
    print(f"测试结果: {len(result)} 个端口")

asyncio.run(test())
```

## 获取帮助

- 查看命令帮助：`python -m mcp_port_scanner --help`
- 查看开发文档：[DEVELOPMENT_GUIDE.md](./DEVELOPMENT_GUIDE.md)
- 查看API文档：[API_REFERENCE.md](./API_REFERENCE.md)
- 提交Issue：[GitHub Issues](https://github.com/yourusername/mcp-port-scanner/issues)

---

祝您使用愉快！如有问题，欢迎反馈。 