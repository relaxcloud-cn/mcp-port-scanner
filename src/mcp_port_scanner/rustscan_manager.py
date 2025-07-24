"""
RustScan 二进制文件管理器
处理跨平台 RustScan 二进制文件的路径解析和管理
"""

import os
import platform
import subprocess
from pathlib import Path
from typing import Optional, Tuple
from .logger_config import logger


class RustScanManager:
    """RustScan 二进制文件管理器"""
    
    def __init__(self):
        self.project_root = self._get_project_root()
        self.bin_dir = self.project_root / "bin"
        self.platform = self._detect_platform()
        self._rustscan_path: Optional[Path] = None
        
        logger.debug(f"RustScanManager 初始化: 平台={self.platform}, bin目录={self.bin_dir}")
    
    def _get_project_root(self) -> Path:
        """获取项目根目录"""
        # 从当前文件位置向上查找项目根目录
        current_dir = Path(__file__).parent
        while current_dir != current_dir.parent:
            if (current_dir / "pyproject.toml").exists():
                return current_dir
            current_dir = current_dir.parent
        
        # 如果找不到，回退到当前目录的上级
        return Path(__file__).parent.parent.parent
    
    def _detect_platform(self) -> str:
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
            logger.warning(f"未知平台: {system}-{machine}，回退到 linux-x64")
            return "linux-x64"
    
    def get_rustscan_path(self) -> Optional[Path]:
        """
        获取 RustScan 二进制文件路径
        优先使用本地 bin 目录，其次使用系统安装的版本
        
        Returns:
            Path: RustScan 二进制文件路径，如果找不到则返回 None
        """
        if self._rustscan_path and self._rustscan_path.exists():
            return self._rustscan_path
        
        # 1. 检查本地 bin 目录
        local_rustscan = self._get_local_rustscan_path()
        if local_rustscan and local_rustscan.exists():
            logger.info(f"使用本地 RustScan: {local_rustscan}")
            self._rustscan_path = local_rustscan
            return local_rustscan
        
        # 2. 检查系统安装的 RustScan
        system_rustscan = self._get_system_rustscan_path()
        if system_rustscan:
            logger.info(f"使用系统 RustScan: {system_rustscan}")
            self._rustscan_path = Path(system_rustscan)
            return self._rustscan_path
        
        # 3. 都找不到
        logger.warning("未找到 RustScan 二进制文件")
        return None
    
    def _get_local_rustscan_path(self) -> Optional[Path]:
        """获取本地 bin 目录中的 RustScan 路径"""
        filename_map = {
            "windows-x64": "rustscan-windows-x64.exe",
            "linux-x64": "rustscan-linux-x64",
            "macos-x64": "rustscan-macos-x64", 
            "macos-arm64": "rustscan-macos-arm64"
        }
        
        filename = filename_map.get(self.platform)
        if not filename:
            return None
        
        rustscan_path = self.bin_dir / filename
        return rustscan_path if rustscan_path.exists() else None
    
    def _get_system_rustscan_path(self) -> Optional[str]:
        """获取系统安装的 RustScan 路径"""
        try:
            if self.platform == "windows-x64":
                # Windows: 检查 PATH
                result = subprocess.run(["where", "rustscan"], 
                                      capture_output=True, text=True)
            else:
                # Linux/macOS: 检查 which
                result = subprocess.run(["which", "rustscan"], 
                                      capture_output=True, text=True)
            
            if result.returncode == 0:
                return result.stdout.strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass
        
        return None
    
    def verify_rustscan(self) -> Tuple[bool, str]:
        """
        验证 RustScan 是否可用
        
        Returns:
            Tuple[bool, str]: (是否可用, 版本信息或错误信息)
        """
        rustscan_path = self.get_rustscan_path()
        if not rustscan_path:
            return False, "未找到 RustScan 二进制文件"
        
        try:
            result = subprocess.run([str(rustscan_path), "--version"], 
                                  capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                version_info = result.stdout.strip()
                logger.info(f"RustScan 验证成功: {version_info}")
                return True, version_info
            else:
                error_msg = result.stderr.strip() or "未知错误"
                logger.error(f"RustScan 验证失败: {error_msg}")
                return False, f"RustScan 执行失败: {error_msg}"
                
        except subprocess.TimeoutExpired:
            return False, "RustScan 验证超时"
        except Exception as e:
            return False, f"RustScan 验证异常: {str(e)}"
    
    def check_installation(self) -> dict:
        """
        检查 RustScan 安装状态
        
        Returns:
            dict: 安装状态信息
        """
        status = {
            "platform": self.platform,
            "bin_dir": str(self.bin_dir),
            "local_available": False,
            "local_path": None,
            "system_available": False,
            "system_path": None,
            "current_path": None,
            "verified": False,
            "version": None,
            "suggestions": []
        }
        
        # 检查本地安装
        local_path = self._get_local_rustscan_path()
        if local_path and local_path.exists():
            status["local_available"] = True
            status["local_path"] = str(local_path)
        
        # 检查系统安装
        system_path = self._get_system_rustscan_path()
        if system_path:
            status["system_available"] = True
            status["system_path"] = system_path
        
        # 检查当前使用的路径
        current_path = self.get_rustscan_path()
        if current_path:
            status["current_path"] = str(current_path)
            
            # 验证
            verified, version_info = self.verify_rustscan()
            status["verified"] = verified
            status["version"] = version_info
        
        # 生成建议
        if not status["local_available"] and not status["system_available"]:
            status["suggestions"].append("运行 'python scripts/download_rustscan.py' 下载本地版本")
            status["suggestions"].append("或使用包管理器安装系统版本")
        elif not status["verified"]:
            status["suggestions"].append("RustScan 无法正常运行，请检查文件权限")
            if self.platform != "windows-x64":
                status["suggestions"].append("尝试运行 'chmod +x " + str(current_path) + "'")
        
        return status
    
    def get_command_args(self, target_ip: str, **kwargs) -> list:
        """
        构建 RustScan 命令参数
        
        Args:
            target_ip: 目标IP地址
            **kwargs: 其他参数
                - ports: 端口列表或端口范围
                - timeout: 超时时间(ms)
                - batch_size: 批处理大小
                - tries: 重试次数
                - ulimit: 文件描述符限制
                - port_range: 端口范围字符串 (例如: "1-1000")
        
        Returns:
            list: 命令参数列表
        """
        rustscan_path = self.get_rustscan_path()
        if not rustscan_path:
            raise FileNotFoundError("RustScan 二进制文件未找到")
        
        cmd = [str(rustscan_path)]
        
        # 基本参数
        cmd.extend(["-a", target_ip])
        
        # 可选参数
        if "timeout" in kwargs:
            cmd.extend(["-t", str(kwargs["timeout"])])
        
        if "batch_size" in kwargs:
            cmd.extend(["-b", str(kwargs["batch_size"])])
            
        if "tries" in kwargs:
            cmd.extend(["--tries", str(kwargs["tries"])])
            
        if "ulimit" in kwargs:
            cmd.extend(["--ulimit", str(kwargs["ulimit"])])
        
        # 输出格式
        cmd.append("-g")  # greppable 输出
        
        # 扫描顺序
        cmd.extend(["--scan-order", "serial"])
        
        # 端口设置
        if "ports" in kwargs:
            ports = kwargs["ports"]
            if isinstance(ports, list):
                ports_str = ",".join(map(str, ports))
                cmd.extend(["-p", ports_str])
            else:
                cmd.extend(["-p", str(ports)])
        elif "port_range" in kwargs:
            cmd.extend(["-r", kwargs["port_range"]])
        
        return cmd
    
    def install_suggestions(self) -> str:
        """
        获取安装建议
        
        Returns:
            str: 安装建议文本
        """
        suggestions = []
        
        suggestions.append("🔧 RustScan 安装建议：")
        suggestions.append("")
        
        suggestions.append("方法1: 自动下载（推荐）")
        suggestions.append("  python scripts/download_rustscan.py")
        suggestions.append("")
        
        if self.platform == "linux-x64":
            suggestions.append("方法2: 系统包管理器")
            suggestions.append("  # Ubuntu/Debian")
            suggestions.append("  wget https://github.com/RustScan/RustScan/releases/download/2.0.1/rustscan_2.0.1_amd64.deb")
            suggestions.append("  sudo dpkg -i rustscan_2.0.1_amd64.deb")
            suggestions.append("")
        elif self.platform.startswith("macos"):
            suggestions.append("方法2: Homebrew")
            suggestions.append("  brew install rustscan")
            suggestions.append("")
        elif self.platform == "windows-x64":
            suggestions.append("方法2: 手动下载")
            suggestions.append("  1. 访问 https://github.com/RustScan/RustScan/releases")
            suggestions.append("  2. 下载 Windows 版本")
            suggestions.append("  3. 重命名为 rustscan-windows-x64.exe")
            suggestions.append("  4. 放置到 bin/ 目录")
            suggestions.append("")
        
        suggestions.append("方法3: Docker 环境")
        suggestions.append("  docker-compose up -d mcp-port-scanner")
        
        return "\n".join(suggestions)


# 全局实例
_rustscan_manager: Optional[RustScanManager] = None


def get_rustscan_manager() -> RustScanManager:
    """获取 RustScan 管理器单例"""
    global _rustscan_manager
    if _rustscan_manager is None:
        _rustscan_manager = RustScanManager()
    return _rustscan_manager 