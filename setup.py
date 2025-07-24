#!/usr/bin/env python3
"""
MCP Port Scanner 安装脚本
自动化安装和配置过程
"""

import os
import sys
import subprocess
from pathlib import Path
from setuptools import setup, find_packages
from setuptools.command.install import install
from setuptools.command.develop import develop


class PostInstallCommand(install):
    """安装后执行的命令"""
    
    def run(self):
        install.run(self)
        self.post_install()
    
    def post_install(self):
        """安装后处理"""
        print("🚀 MCP Port Scanner 安装完成！")
        
        # 尝试下载 RustScan
        try:
            print("📥 正在下载 RustScan...")
            script_path = Path(__file__).parent / "scripts" / "download_rustscan.py"
            
            if script_path.exists():
                result = subprocess.run([sys.executable, str(script_path)], 
                                      capture_output=True, text=True)
                
                if result.returncode == 0:
                    print("✅ RustScan 下载成功！")
                else:
                    print("⚠️ RustScan 自动下载失败，请手动下载：")
                    print("   python scripts/download_rustscan.py")
            else:
                print("⚠️ 下载脚本未找到，请手动下载 RustScan")
                
        except Exception as e:
            print(f"⚠️ RustScan 下载过程中出现错误: {e}")
        
        print("\n📖 安装完成提示：")
        print("1. 验证安装：mcp-port-scanner rustscan")
        print("2. 快速测试：mcp-port-scanner scan 8.8.8.8")
        print("3. 配置 Cursor：参考 README.md 中的 MCP 配置")


class PostDevelopCommand(develop):
    """开发模式安装后执行的命令"""
    
    def run(self):
        develop.run(self)
        PostInstallCommand.post_install(self)


# 读取 requirements
def read_requirements():
    requirements_path = Path(__file__).parent / "requirements.txt"
    if requirements_path.exists():
        with open(requirements_path, 'r', encoding='utf-8') as f:
            return [line.strip() for line in f if line.strip() and not line.startswith('#')]
    return []


# 读取 README
def read_readme():
    readme_path = Path(__file__).parent / "README.md"
    if readme_path.exists():
        with open(readme_path, 'r', encoding='utf-8') as f:
            return f.read()
    return ""


if __name__ == "__main__":
    setup(
        name="mcp-port-scanner",
        version="0.1.1",
        description="基于MCP协议的智能分层端口扫描服务",
        long_description=read_readme(),
        long_description_content_type="text/markdown",
        author="Sky",
        author_email="sky@example.com",
        url="https://github.com/relaxcloud-cn/mcp-port-scanner",
        packages=find_packages(where="src"),
        package_dir={"": "src"},
        install_requires=read_requirements(),
        python_requires=">=3.8",
        entry_points={
            "console_scripts": [
                "mcp-port-scanner=mcp_port_scanner.interfaces.cli_interface:main",
            ],
        },
        include_package_data=True,
        package_data={
            "mcp_port_scanner": ["../bin/*"],
        },
        classifiers=[
            "Development Status :: 4 - Beta",
            "Intended Audience :: Developers",
            "Intended Audience :: System Administrators",
            "Topic :: Security",
            "Topic :: System :: Networking",
            "License :: OSI Approved :: MIT License",
            "Programming Language :: Python :: 3",
            "Programming Language :: Python :: 3.8",
            "Programming Language :: Python :: 3.9",
            "Programming Language :: Python :: 3.10",
            "Programming Language :: Python :: 3.11",
            "Programming Language :: Python :: 3.12",
        ],
        cmdclass={
            'install': PostInstallCommand,
            'develop': PostDevelopCommand,
        },
        zip_safe=False,
    ) 