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

# 复制 RustScan 二进制文件（已在本地 bin/ 目录）
COPY bin/ bin/

# 赋予可执行权限（Linux下）
RUN chmod +x bin/rustscan-*

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