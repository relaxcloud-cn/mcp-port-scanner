#!/usr/bin/env python3
"""
自动下载 RustScan 二进制文件脚本
支持多平台自动识别和下载
"""

import os
import sys
import platform
import subprocess
import urllib.request
import zipfile
import tarfile
import shutil
from pathlib import Path
from typing import Dict, Tuple, Optional
import argparse


# RustScan 版本和下载配置
RUSTSCAN_VERSION = "2.0.1"
RUSTSCAN_RELEASES_URL = f"https://github.com/RustScan/RustScan/releases/download/{RUSTSCAN_VERSION}"

# 平台配置映射
PLATFORM_CONFIG = {
    "windows-x64": {
        "url": f"{RUSTSCAN_RELEASES_URL}/rustscan_{RUSTSCAN_VERSION}_amd64.deb",
        "filename": "rustscan-windows-x64.exe",
        "archive_type": None,  # 直接下载可执行文件
    },
    "linux-x64": {
        "url": f"{RUSTSCAN_RELEASES_URL}/rustscan_{RUSTSCAN_VERSION}_amd64.deb",
        "filename": "rustscan-linux-x64",
        "archive_type": "deb",
    },
    "macos-x64": {
        "url": f"{RUSTSCAN_RELEASES_URL}/rustscan_{RUSTSCAN_VERSION}_amd64.deb",
        "filename": "rustscan-macos-x64",
        "archive_type": "deb",
    },
    "macos-arm64": {
        "url": f"{RUSTSCAN_RELEASES_URL}/rustscan_{RUSTSCAN_VERSION}_amd64.deb",
        "filename": "rustscan-macos-arm64", 
        "archive_type": "deb",
    }
}

# GitHub 直接下载链接（更可靠的方案）
DIRECT_DOWNLOAD_URLS = {
    "windows-x64": "https://github.com/RustScan/RustScan/releases/download/2.0.1/rustscan_2.0.1_amd64.deb",
    "linux-x64": "https://github.com/RustScan/RustScan/releases/download/2.0.1/rustscan_2.0.1_amd64.deb",
    "macos-x64": "https://github.com/RustScan/RustScan/releases/download/2.0.1/rustscan_2.0.1_amd64.deb",
    "macos-arm64": "https://github.com/RustScan/RustScan/releases/download/2.0.1/rustscan_2.0.1_amd64.deb"
}


def get_project_root() -> Path:
    """获取项目根目录"""
    current_dir = Path(__file__).parent
    # 脚本在 scripts/ 目录中，向上一级是项目根目录
    return current_dir.parent


def get_bin_dir() -> Path:
    """获取 bin 目录路径"""
    bin_dir = get_project_root() / "bin"
    bin_dir.mkdir(exist_ok=True)
    return bin_dir


def detect_platform() -> str:
    """检测当前平台"""
    system = platform.system().lower()
    machine = platform.machine().lower()
    
    if system == "windows":
        return "windows-x64"
    elif system == "linux":
        return "linux-x64"
    elif system == "darwin":  # macOS
        if machine in ["arm64", "aarch64"]:
            return "macos-arm64"
        else:
            return "macos-x64"
    else:
        raise ValueError(f"不支持的平台: {system}-{machine}")


def download_file(url: str, destination: Path) -> bool:
    """下载文件"""
    try:
        print(f"📥 正在下载: {url}")
        print(f"📁 保存到: {destination}")
        
        with urllib.request.urlopen(url) as response:
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            with open(destination, 'wb') as f:
                while True:
                    chunk = response.read(8192)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    
                    if total_size > 0:
                        progress = (downloaded / total_size) * 100
                        print(f"\r📊 下载进度: {progress:.1f}%", end="", flush=True)
        
        print(f"\n✅ 下载完成: {destination.name}")
        return True
        
    except Exception as e:
        print(f"\n❌ 下载失败: {e}")
        return False


def extract_deb_package(deb_path: Path, output_path: Path) -> bool:
    """从 .deb 包中提取 RustScan 二进制文件"""
    try:
        print(f"📦 正在提取: {deb_path.name}")
        
        # 创建临时目录
        temp_dir = deb_path.parent / "temp_extract"
        temp_dir.mkdir(exist_ok=True)
        
        try:
            # 使用 ar 命令提取 .deb 包（如果可用）
            subprocess.run(["ar", "x", str(deb_path)], cwd=temp_dir, check=True)
            
            # 找到 data.tar.xz 或类似文件
            data_files = list(temp_dir.glob("data.tar.*"))
            if not data_files:
                raise FileNotFoundError("未找到 data.tar 文件")
            
            data_file = data_files[0]
            
            # 提取 data.tar
            with tarfile.open(data_file) as tar:
                tar.extractall(temp_dir)
            
            # 查找 RustScan 二进制文件
            rustscan_paths = [
                temp_dir / "usr" / "bin" / "rustscan",
                temp_dir / "bin" / "rustscan",
            ]
            
            for rustscan_path in rustscan_paths:
                if rustscan_path.exists():
                    shutil.copy2(rustscan_path, output_path)
                    output_path.chmod(0o755)  # 设置执行权限
                    print(f"✅ 提取完成: {output_path.name}")
                    return True
            
            raise FileNotFoundError("在 .deb 包中未找到 rustscan 二进制文件")
            
        finally:
            # 清理临时目录
            shutil.rmtree(temp_dir, ignore_errors=True)
            
    except subprocess.CalledProcessError:
        print("⚠️ 系统未安装 ar 命令，尝试其他方法...")
        return False
    except Exception as e:
        print(f"❌ 提取失败: {e}")
        return False


def install_via_package_manager(platform: str) -> bool:
    """通过包管理器安装 RustScan"""
    bin_dir = get_bin_dir()
    
    if platform.startswith("linux"):
        # Linux: 尝试 wget + dpkg
        try:
            deb_file = bin_dir / "rustscan.deb"
            
            # 下载 .deb 包
            if not download_file(DIRECT_DOWNLOAD_URLS[platform], deb_file):
                return False
            
            # 提取二进制文件
            output_file = bin_dir / PLATFORM_CONFIG[platform]["filename"]
            if extract_deb_package(deb_file, output_file):
                deb_file.unlink()  # 删除临时 .deb 文件
                return True
            
        except Exception as e:
            print(f"❌ 包管理器安装失败: {e}")
    
    return False


def download_rustscan_for_platform(platform: str) -> bool:
    """下载指定平台的 RustScan"""
    print(f"🎯 开始下载 RustScan ({platform})")
    
    bin_dir = get_bin_dir()
    config = PLATFORM_CONFIG[platform]
    output_file = bin_dir / config["filename"]
    
    # 如果文件已存在，询问是否覆盖
    if output_file.exists():
        response = input(f"文件 {output_file.name} 已存在，是否覆盖? (y/N): ")
        if response.lower() != 'y':
            print("跳过下载")
            return True
    
    # 对于 Linux 平台，优先尝试包管理器
    if platform.startswith("linux") or platform.startswith("macos"):
        if install_via_package_manager(platform):
            return True
    
    # Windows 或其他平台，尝试直接下载
    download_url = DIRECT_DOWNLOAD_URLS.get(platform)
    if not download_url:
        print(f"❌ 平台 {platform} 暂不支持自动下载")
        return False
    
    # 对于 Windows，我们需要特殊处理
    if platform == "windows-x64":
        print("⚠️ Windows 平台需要手动下载和配置")
        print("请访问：https://github.com/RustScan/RustScan/releases")
        print("下载 Windows 版本并重命名为：rustscan-windows-x64.exe")
        return False
    
    # 下载文件
    temp_file = bin_dir / f"temp_{config['filename']}"
    if download_file(download_url, temp_file):
        if temp_file.suffix == ".deb":
            # .deb 包需要提取
            if extract_deb_package(temp_file, output_file):
                temp_file.unlink()
                return True
        else:
            # 直接重命名
            temp_file.rename(output_file)
            output_file.chmod(0o755)
            return True
    
    return False


def verify_rustscan(platform: str) -> bool:
    """验证 RustScan 是否正常工作"""
    bin_dir = get_bin_dir()
    config = PLATFORM_CONFIG[platform]
    rustscan_path = bin_dir / config["filename"]
    
    if not rustscan_path.exists():
        print(f"❌ 文件不存在: {rustscan_path}")
        return False
    
    try:
        # 测试运行
        result = subprocess.run([str(rustscan_path), "--version"], 
                               capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            print(f"✅ RustScan 验证成功: {result.stdout.strip()}")
            return True
        else:
            print(f"❌ RustScan 运行失败: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ 验证失败: {e}")
        return False


def show_manual_instructions():
    """显示手动安装说明"""
    print("\n📖 手动安装说明：")
    print("1. 访问：https://github.com/RustScan/RustScan/releases/tag/2.0.1")
    print("2. 下载对应平台的文件：")
    print("   - Windows: 下载 Windows 版本")
    print("   - Linux: 下载 rustscan_2.0.1_amd64.deb")
    print("   - macOS: 下载 macOS 版本")
    print("3. 将文件放置到 bin/ 目录并重命名：")
    for platform, config in PLATFORM_CONFIG.items():
        print(f"   - {platform}: {config['filename']}")
    print("4. 设置执行权限（Linux/macOS）：chmod +x bin/rustscan-*")


def main():
    parser = argparse.ArgumentParser(description="下载 RustScan 二进制文件")
    parser.add_argument("--all", action="store_true", help="下载所有平台的二进制文件")
    parser.add_argument("--platform", help="指定平台 (windows-x64, linux-x64, macos-x64, macos-arm64)")
    parser.add_argument("--verify", action="store_true", help="仅验证现有文件")
    
    args = parser.parse_args()
    
    print("🚀 RustScan 二进制文件管理工具")
    print(f"📁 项目根目录: {get_project_root()}")
    print(f"📁 二进制目录: {get_bin_dir()}")
    print()
    
    if args.verify:
        # 仅验证
        current_platform = detect_platform()
        success = verify_rustscan(current_platform)
        sys.exit(0 if success else 1)
    
    if args.all:
        # 下载所有平台
        print("📦 下载所有平台的 RustScan...")
        success_count = 0
        for platform in PLATFORM_CONFIG.keys():
            if download_rustscan_for_platform(platform):
                success_count += 1
        
        print(f"\n📊 完成！成功下载 {success_count}/{len(PLATFORM_CONFIG)} 个平台")
        
    elif args.platform:
        # 下载指定平台
        if args.platform not in PLATFORM_CONFIG:
            print(f"❌ 不支持的平台: {args.platform}")
            print(f"支持的平台: {', '.join(PLATFORM_CONFIG.keys())}")
            sys.exit(1)
        
        success = download_rustscan_for_platform(args.platform)
        if success:
            verify_rustscan(args.platform)
        
    else:
        # 下载当前平台
        try:
            current_platform = detect_platform()
            print(f"🔍 检测到平台: {current_platform}")
            
            success = download_rustscan_for_platform(current_platform)
            if success:
                verify_rustscan(current_platform)
            else:
                show_manual_instructions()
                
        except ValueError as e:
            print(f"❌ {e}")
            show_manual_instructions()
            sys.exit(1)


if __name__ == "__main__":
    main() 