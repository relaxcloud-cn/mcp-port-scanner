"""
统一的日志配置模块
提供详细的日志格式，包含文件名、函数名、行号等信息
"""

import sys
import os
from pathlib import Path
from loguru import logger

# 移除默认的 handler
logger.remove()

# 自定义日志格式化函数
def detailed_formatter(record):
    """
    详细的日志格式化器，包含：
    - 时间戳
    - 日志级别
    - 文件路径（相对路径）
    - 函数名
    - 行号
    - 消息内容
    - 异常信息（如果有）
    """
    # 获取相对路径
    try:
        # 获取项目根目录
        project_root = Path(__file__).parent.parent.parent
        filepath = Path(record["file"].path)
        relative_path = filepath.relative_to(project_root)
    except (ValueError, AttributeError):
        relative_path = Path(record["file"].path).name if record["file"].path else "unknown"
    
    # 构建格式
    time_format = "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green>"
    level_format = "<level>{level: <8}</level>"
    location_format = "<cyan>{}</cyan>:<yellow>{}</yellow>:<blue>{}</blue>".format(
        relative_path,
        record["function"],
        record["line"]
    )
    message_format = "<level>{message}</level>"
    
    # 组合最终格式
    log_format = f"{time_format} | {level_format} | {location_format} | {message_format}"
    
    # 添加异常信息
    if record["exception"]:
        log_format += "\n{exception}"
    else:
        log_format += "\n"
    
    return log_format

# 简化的格式化器（用于生产环境）
def simple_formatter(record):
    """简化的日志格式化器"""
    return "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | <level>{message}</level>\n{exception}"

# 配置日志输出
def configure_logger(level="INFO", detailed=True, log_file=None):
    """
    配置日志系统
    
    Args:
        level: 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        detailed: 是否使用详细格式
        log_file: 日志文件路径（可选）
    """
    # 选择格式化器
    formatter = detailed_formatter if detailed else simple_formatter
    
    # 添加控制台输出
    logger.add(
        sys.stderr,
        format=formatter,
        level=level,
        colorize=True,
        backtrace=True,
        diagnose=True,
        enqueue=True  # 异步日志，提高性能
    )
    
    # 添加文件输出（如果指定）
    if log_file:
        logger.add(
            log_file,
            format=formatter,
            level=level,
            rotation="100 MB",  # 日志轮转
            retention="7 days",  # 保留7天
            compression="zip",  # 压缩旧日志
            backtrace=True,
            diagnose=True,
            enqueue=True
        )

# 从环境变量读取配置
def init_logger():
    """初始化日志系统，从环境变量读取配置"""
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    log_detailed = os.getenv("LOG_DETAILED", "true").lower() == "true"
    log_file = os.getenv("LOG_FILE", "logs/mcp_port_scanner.log")

    print(f"log_file: {log_file}")
    print(f"log_level: {log_level}")
    print(f"log_detailed: {log_detailed}")
    
    configure_logger(level=log_level, detailed=log_detailed, log_file=log_file)

# 默认初始化
init_logger()

# 导出配置好的 logger
__all__ = ["logger", "configure_logger", "init_logger"] 