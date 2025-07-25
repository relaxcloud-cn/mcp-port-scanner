@echo off
REM DXT扩展包构建脚本 (Windows)

echo 开始构建MCP Port Scanner DXT扩展...

REM 切换到项目根目录
cd /d "%~dp0\.."

REM 检查Python是否安装
python --version >nul 2>&1
if errorlevel 1 (
    echo 错误: 需要Python 3.8或更高版本
    echo 请从 https://www.python.org 安装Python
    exit /b 1
)

REM 检查manifest.json是否存在
if not exist "manifest.json" (
    echo 错误: 未找到manifest.json文件
    echo 请先创建manifest.json文件
    exit /b 1
)

REM 执行Python构建脚本
python scripts\build-dxt.py

REM 检查构建结果
if %errorlevel% equ 0 (
    echo.
    echo ✅ 构建成功!
    echo.
    echo 现在可以：
    echo 1. 使用 'dxt info mcp-port-scanner-*.dxt' 查看扩展信息
    echo 2. 直接在Claude Desktop中打开.dxt文件进行安装
) else (
    echo.
    echo ❌ 构建失败，请检查错误信息
    exit /b 1
)

pause 