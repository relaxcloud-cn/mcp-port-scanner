@echo off
chcp 65001 >nul
echo 🐳 MCP端口扫描器 Docker启动脚本
echo.

:menu
echo 请选择运行模式：
echo 1. HTTP服务器模式 (Web界面 + API, 端口8080)
echo 2. MCP服务器模式 (Cursor集成)
echo 3. 命令行模式 (交互式扫描)
echo 4. 构建Docker镜像
echo 5. 停止所有服务
echo 6. 查看服务状态
echo 7. 退出
echo.

set /p choice="请输入选项 (1-7): "

if "%choice%"=="1" goto http_mode
if "%choice%"=="2" goto mcp_mode
if "%choice%"=="3" goto cli_mode
if "%choice%"=="4" goto build
if "%choice%"=="5" goto stop
if "%choice%"=="6" goto status
if "%choice%"=="7" goto exit
goto menu

:http_mode
echo 🚀 启动HTTP服务器模式...
docker-compose up -d mcp-port-scanner-http
echo.
echo ✅ HTTP服务器已启动！
echo 📱 Web界面: http://localhost:8080
echo 📡 API文档: http://localhost:8080/docs
goto menu

:mcp_mode
echo 🚀 启动MCP服务器模式...
docker-compose up -d mcp-port-scanner
echo.
echo ✅ MCP服务器已启动！用于Cursor集成
goto menu

:cli_mode
echo 🚀 启动命令行模式...
docker-compose up -d mcp-port-scanner-cli
echo.
echo 进入容器交互模式...
docker exec -it mcp-port-scanner-cli /bin/bash
goto menu

:build
echo 🔨 构建Docker镜像...
docker-compose build --no-cache
echo.
echo ✅ 镜像构建完成！
goto menu

:stop
echo 🛑 停止所有服务...
docker-compose down
echo.
echo ✅ 所有服务已停止！
goto menu

:status
echo 📊 查看服务状态...
docker-compose ps
echo.
pause
goto menu

:exit
echo 👋 再见！
exit /b 0 