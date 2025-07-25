#!/usr/bin/env python3
"""
DXT扩展包构建脚本
用于将MCP端口扫描服务打包成.dxt文件
"""

import os
import sys
import shutil
import subprocess
import tempfile
import zipfile
import platform
from pathlib import Path

def run_command(cmd, cwd=None):
    """执行命令并返回结果"""
    print(f"执行命令: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"错误: {result.stderr}")
        sys.exit(1)
    return result.stdout

def create_dxt_structure(temp_dir):
    """创建DXT扩展的目录结构"""
    # 创建必要的目录
    server_dir = temp_dir / "server"
    server_dir.mkdir(exist_ok=True)
    
    src_dir = server_dir / "src"
    lib_dir = server_dir / "lib"
    bin_dir = server_dir / "bin"
    config_dir = server_dir / "config"
    
    src_dir.mkdir(exist_ok=True)
    lib_dir.mkdir(exist_ok=True)
    bin_dir.mkdir(exist_ok=True)
    config_dir.mkdir(exist_ok=True)
    
    return server_dir, src_dir, lib_dir, bin_dir, config_dir

def copy_source_files(src_dir, project_root):
    """复制源代码文件"""
    print("复制源代码文件...")
    src_path = project_root / "src"
    if src_path.exists():
        shutil.copytree(src_path, src_dir, dirs_exist_ok=True)
    else:
        print("警告: 未找到src目录")

def copy_rustscan_binaries(bin_dir, project_root):
    """复制RustScan二进制文件"""
    print("复制RustScan二进制文件...")
    bin_path = project_root / "bin"
    if bin_path.exists():
        for file in bin_path.iterdir():
            if file.is_file():
                shutil.copy2(file, bin_dir / file.name)
                # 设置可执行权限
                if not file.name.endswith('.exe'):
                    os.chmod(bin_dir / file.name, 0o755)
    else:
        print("警告: 未找到bin目录")

def copy_config_files(config_dir, project_root):
    """复制配置文件"""
    print("复制配置文件...")
    config_path = project_root / "config"
    if config_path.exists():
        for file in config_path.iterdir():
            if file.is_file():
                shutil.copy2(file, config_dir / file.name)

def install_dependencies(lib_dir, project_root):
    """安装Python依赖到lib目录"""
    print("安装Python依赖...")
    
    # 创建临时requirements文件，只包含运行时依赖
    temp_req = lib_dir.parent / "requirements-runtime.txt"
    with open(temp_req, 'w') as f:
        f.write("""mcp>=1.0,<2.0
asyncio-pool>=0.6.0
pydantic>=2.0.0
loguru>=0.7.0
click>=8.0.0
rich>=13.0.0
httpx>=0.25.0
fastapi>=0.104.0
uvicorn[standard]>=0.24.0""")
    
    # 使用pip安装到lib目录
    run_command([
        sys.executable, "-m", "pip", "install",
        "-r", str(temp_req),
        "-t", str(lib_dir),
        "--no-deps",  # 不安装依赖的依赖
        "--no-compile"  # 不编译.pyc文件
    ])
    
    # 然后安装所有依赖
    run_command([
        sys.executable, "-m", "pip", "install",
        "-r", str(temp_req),
        "-t", str(lib_dir),
        "--no-compile"
    ])
    
    # 删除临时文件
    temp_req.unlink()
    
    # 清理不必要的文件
    print("清理不必要的文件...")
    for item in lib_dir.rglob("*.dist-info"):
        shutil.rmtree(item)
    for item in lib_dir.rglob("__pycache__"):
        shutil.rmtree(item)
    for item in lib_dir.rglob("*.pyc"):
        item.unlink()
    for item in lib_dir.rglob("*.pyo"):
        item.unlink()

def copy_manifest(temp_dir, project_root):
    """复制manifest.json文件"""
    print("复制manifest.json...")
    manifest_src = project_root / "manifest.json"
    if manifest_src.exists():
        shutil.copy2(manifest_src, temp_dir / "manifest.json")
    else:
        print("错误: 未找到manifest.json文件")
        sys.exit(1)

def create_dxt_archive(temp_dir, output_path):
    """创建.dxt压缩文件"""
    print(f"创建DXT文件: {output_path}")
    
    with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(temp_dir):
            for file in files:
                file_path = Path(root) / file
                arcname = file_path.relative_to(temp_dir)
                zipf.write(file_path, arcname)

def main():
    """主函数"""
    print("MCP Port Scanner DXT构建脚本")
    print("=" * 50)
    
    # 获取项目根目录
    project_root = Path(__file__).parent.parent
    
    # 输出文件名
    output_name = "mcp-port-scanner-0.1.1.dxt"
    output_path = project_root / output_name
    
    # 创建临时目录
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        print(f"使用临时目录: {temp_path}")
        
        # 创建DXT结构
        server_dir, src_dir, lib_dir, bin_dir, config_dir = create_dxt_structure(temp_path)
        
        # 复制文件
        copy_manifest(temp_path, project_root)
        copy_source_files(src_dir, project_root)
        copy_rustscan_binaries(bin_dir, project_root)
        copy_config_files(config_dir, project_root)
        
        # 安装依赖
        install_dependencies(lib_dir, project_root)
        
        # 创建DXT压缩文件
        create_dxt_archive(temp_path, output_path)
    
    print(f"\n✅ DXT文件创建成功: {output_path}")
    print(f"文件大小: {output_path.stat().st_size / 1024 / 1024:.2f} MB")
    
    # 提示后续步骤
    print("\n后续步骤:")
    print("1. 安装DXT CLI工具: npm install -g @anthropic-ai/dxt")
    print("2. 验证manifest: dxt validate manifest.json")
    print(f"3. 查看扩展信息: dxt info {output_name}")
    print(f"4. (可选)签名扩展: dxt sign {output_name} --self-signed")
    print(f"5. 在Claude Desktop中打开{output_name}文件进行安装")

if __name__ == "__main__":
    main() 