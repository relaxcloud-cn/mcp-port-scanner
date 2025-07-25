#!/bin/bash
# DXT扩展包构建脚本

echo "开始构建MCP Port Scanner DXT扩展..."

# 切换到项目根目录
cd "$(dirname "$0")/.." || exit 1

# 检查Python是否安装
if ! command -v python3 &> /dev/null; then
    echo "错误: 需要Python 3.8或更高版本"
    exit 1
fi

# 检查manifest.json是否存在
if [ ! -f "manifest.json" ]; then
    echo "错误: 未找到manifest.json文件"
    echo "请先创建manifest.json文件"
    exit 1
fi

# 执行Python构建脚本
python3 scripts/build-dxt.py

# 检查构建结果
if [ $? -eq 0 ]; then
    echo ""
    echo "✅ 构建成功!"
    echo ""
    echo "现在可以："
    echo "1. 使用 'dxt info mcp-port-scanner-*.dxt' 查看扩展信息"
    echo "2. 直接在Claude Desktop中打开.dxt文件进行安装"
else
    echo ""
    echo "❌ 构建失败，请检查错误信息"
    exit 1
fi 