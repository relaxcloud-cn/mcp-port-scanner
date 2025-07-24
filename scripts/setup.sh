#!/bin/bash
# MCP Port Scanner 一键安装脚本

set -e

echo "🚀 MCP Port Scanner 一键安装脚本"
echo "================================="

# 检查 Python 版本
check_python() {
    if ! command -v python3 &> /dev/null; then
        echo "❌ Python 3 未安装，请先安装 Python 3.8+"
        exit 1
    fi
    
    python_version=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    echo "✅ Python 版本: $python_version"
    
    if ! python3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)"; then
        echo "❌ Python 版本需要 3.8 或更高，当前版本: $python_version"
        exit 1
    fi
}

# 安装项目依赖
install_dependencies() {
    echo "📦 安装 Python 依赖..."
    
    # 检查是否有 pip
    if ! command -v pip3 &> /dev/null; then
        echo "❌ pip3 未安装，请先安装 pip"
        exit 1
    fi
    
    # 安装依赖
    pip3 install -r requirements.txt
    pip3 install mcp
    
    echo "✅ Python 依赖安装完成"
}

# 下载 RustScan
download_rustscan() {
    echo "⬇️ 下载 RustScan..."
    
    if python3 scripts/download_rustscan.py; then
        echo "✅ RustScan 下载成功"
    else
        echo "⚠️ RustScan 自动下载失败"
        echo "💡 请手动下载或使用系统包管理器安装"
        echo "   参考: bin/README.md"
    fi
}

# 验证安装
verify_installation() {
    echo "🔍 验证安装..."
    
    # 验证 Python 模块
    if python3 -c "import mcp_port_scanner" 2>/dev/null; then
        echo "✅ Python 模块导入成功"
    else
        echo "❌ Python 模块导入失败"
        exit 1
    fi
    
    # 验证 RustScan
    python3 -c "
from src.mcp_port_scanner.rustscan_manager import get_rustscan_manager
manager = get_rustscan_manager()
verified, info = manager.verify_rustscan()
print('✅ RustScan 验证成功:', info if verified else '⚠️ RustScan 不可用:', info)
"
}

# 显示使用说明
show_usage() {
    echo ""
    echo "🎉 安装完成！"
    echo "============="
    echo ""
    echo "📋 快速开始："
    echo "  # 检查 RustScan 状态"
    echo "  python -m mcp_port_scanner.interfaces.cli_interface rustscan"
    echo ""
    echo "  # 测试扫描"
    echo "  python -m mcp_port_scanner.interfaces.cli_interface scan 8.8.8.8"
    echo ""
    echo "📖 更多使用方法："
    echo "  • CLI 使用: python -m mcp_port_scanner.interfaces.cli_interface --help"
    echo "  • MCP 配置: 参考 README.md"
    echo "  • Python SDK: 参考 docs/API_REFERENCE.md"
    echo ""
    echo "🐳 Docker 使用："
    echo "  docker-compose up -d mcp-port-scanner"
    echo ""
}

# 主函数
main() {
    echo "开始安装..."
    
    check_python
    install_dependencies
    download_rustscan
    verify_installation
    show_usage
    
    echo "✨ 安装完成！"
}

# 如果是直接运行脚本
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi 