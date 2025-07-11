#!/usr/bin/env python3
"""
简化的端口扫描器入口脚本
"""

import sys
import os

# 添加src到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.mcp_port_scanner.interfaces.cli_interface import main

if __name__ == '__main__':
    main() 