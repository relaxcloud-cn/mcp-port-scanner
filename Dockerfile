# 使用官方Python基础镜像
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    curl \
    wget \
    build-essential \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# 安装RustScan（可选，如果安装失败会回退到socket扫描）
RUN wget https://github.com/RustScan/RustScan/releases/download/2.0.1/rustscan_2.0.1_amd64.deb \
    && (dpkg -i rustscan_2.0.1_amd64.deb || echo "RustScan安装失败，将使用socket扫描") \
    && rm -f rustscan_2.0.1_amd64.deb

# 复制项目文件
COPY pyproject.toml .
COPY src/ src/
COPY config/ config/
COPY examples/ examples/
COPY scan.py .
COPY README.md .

# 创建用户和目录
RUN useradd -m -u 1000 scanner

# 安装Python依赖
RUN pip install --no-cache-dir -e .

# 创建必要目录并设置权限
RUN mkdir -p /app/logs /app/scan_results && \
    chown -R scanner:scanner /app

USER scanner

# 设置环境变量
ENV PYTHONPATH=/app/src
ENV LOG_LEVEL=INFO

# 暴露端口（如果需要MCP服务器）
EXPOSE 8080

# 默认命令（保持容器运行，等待手动启动MCP服务器）
CMD ["tail", "-f", "/dev/null"] 