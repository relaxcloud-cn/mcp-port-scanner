"""
第一层：RustScan基础端口扫描和Banner获取
"""

import asyncio
import socket
import subprocess
import json
import re
import os
from typing import List, Optional, Dict, Any, Tuple
from .logger_config import logger
import time

from .models import PortInfo, ScanTarget, ScanConfig, ServiceProtocol
from .rustscan_manager import get_rustscan_manager


class PortScanner:
    """端口扫描器 - 第一层扫描功能"""
    
    def __init__(self, config: Optional[ScanConfig] = None):
        self.config = config or ScanConfig()
        self.rustscan_manager = get_rustscan_manager()
        
        # 验证 RustScan 可用性
        verified, version_info = self.rustscan_manager.verify_rustscan()
        if verified:
            logger.info(f"RustScan 初始化成功: {version_info}")
        else:
            logger.warning(f"RustScan 初始化失败: {version_info}")
            logger.info("将回退到 Python socket 扫描")
        
        logger.debug("PortScanner 初始化完成，配置: timeout={}ms, batch_size={}", 
                    self.config.rustscan_timeout, self.config.rustscan_batch_size)
    
    async def scan_target(self, target: ScanTarget, progress_callback: Optional[callable] = None) -> List[PortInfo]:
        """
        扫描目标的开放端口
        
        Args:
            target: 扫描目标
            progress_callback: 进度回调函数，参数为(stage, message)
            
        Returns:
            List[PortInfo]: 端口信息列表
        """
        try:
            # Step 1: 端口发现
            if progress_callback:
                await progress_callback("端口发现", "正在扫描端口...")
            
            open_ports = await self._rustscan_ports(target)
            
            if not open_ports:
                logger.info(f"未发现开放端口: {target.ip}")
                return []
            
            # Step 2: Banner抓取
            if progress_callback:
                await progress_callback("Banner抓取", f"正在获取 {len(open_ports)} 个端口的服务信息...")
            
            port_infos = await self._grab_banners(target.ip, open_ports, progress_callback)
            
            logger.info(f"扫描完成: {target.ip}，发现 {len(port_infos)} 个开放端口")
            return port_infos
            
        except Exception as e:
            logger.error(f"端口扫描失败: {target.ip} - {e}")
            return []
    
    async def _rustscan_ports(self, target: ScanTarget) -> List[int]:
        """
        使用RustScan进行端口扫描
        """
        try:
            # 如果指定了端口范围，直接扫描
            if target.ports:
                return await self._execute_rustscan_batch(target, target.ports)
            
            # 全端口扫描：分批处理避免参数过长
            logger.info(f"🔍 开始分批全端口扫描: {target.ip}")
            all_open_ports = []
            
            # 定义扫描批次 - 分成更小的范围
            port_ranges = [
                "1-1000",      # 常用端口
                "1001-5000",   # 扩展端口1
                "5001-10000",  # 扩展端口2
                "10001-20000", # 扩展端口3
                "20001-30000", # 扩展端口4
                "30001-40000", # 扩展端口5
                "40001-50000", # 扩展端口6
                "50001-60000", # 扩展端口7
                "60001-65535"  # 高位端口
            ]
            
            for i, port_range in enumerate(port_ranges, 1):
                logger.info(f"📡 扫描端口范围 {i}/{len(port_ranges)}: {port_range}")
                
                try:
                    batch_ports = await self._execute_rustscan_range(target, port_range)
                    all_open_ports.extend(batch_ports)
                    
                    # 如果这批找到了端口，记录一下
                    if batch_ports:
                        logger.info(f"✅ 范围 {port_range} 发现 {len(batch_ports)} 个开放端口: {batch_ports}")
                        
                except Exception as e:
                    logger.warning(f"⚠️ 范围 {port_range} 扫描失败: {e}")
                    continue
            
            logger.info(f"🎯 全端口扫描完成，总共发现 {len(all_open_ports)} 个开放端口")
            return sorted(list(set(all_open_ports)))  # 去重并排序
                
        except FileNotFoundError:
            logger.warning("RustScan二进制文件未找到，回退到Python socket扫描")
            logger.info(self.rustscan_manager.install_suggestions())
            return await self._socket_scan_ports(target)
        except Exception as e:
            logger.error(f"RustScan扫描失败: {e}")
            return await self._socket_scan_ports(target)

    async def _execute_rustscan_range(self, target: ScanTarget, port_range: str) -> List[int]:
        """
        执行单个端口范围的RustScan扫描
        """
        try:
            cmd = self.rustscan_manager.get_command_args(
                target.ip,
                timeout=self.config.rustscan_timeout,
                batch_size=self.config.rustscan_batch_size,
                tries=self.config.rustscan_tries,
                ulimit=self.config.rustscan_ulimit,
                port_range=port_range
            )
        except FileNotFoundError as e:
            logger.error(f"构建RustScan命令失败: {e}")
            raise
        
        # 执行命令
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            error_msg = stderr.decode().strip()
            if "Permission denied" in error_msg or "ulimit" in error_msg:
                logger.warning(f"RustScan权限或ulimit问题，范围 {port_range}: {error_msg}")
            else:
                logger.warning(f"RustScan范围 {port_range} 执行失败: {error_msg}")
            return []
        
        # 解析结果
        return self._parse_rustscan_greppable_output(stdout.decode())

    async def _execute_rustscan_batch(self, target: ScanTarget, ports: List[int]) -> List[int]:
        """
        执行指定端口列表的RustScan扫描
        """
        # 如果端口数量太多，也需要分批
        if len(ports) > 1000:
            logger.info(f"📋 端口数量 {len(ports)} 较多，分批扫描")
            all_results = []
            batch_size = 1000
            
            for i in range(0, len(ports), batch_size):
                batch_ports = ports[i:i + batch_size]
                logger.info(f"📡 扫描端口批次 {i//batch_size + 1}: {len(batch_ports)} 个端口")
                
                try:
                    batch_results = await self._execute_rustscan_port_list(target, batch_ports)
                    all_results.extend(batch_results)
                except Exception as e:
                    logger.warning(f"⚠️ 端口批次扫描失败: {e}")
                    continue
            
            return sorted(list(set(all_results)))
        else:
            return await self._execute_rustscan_port_list(target, ports)

    async def _execute_rustscan_port_list(self, target: ScanTarget, ports: List[int]) -> List[int]:
        """
        执行具体端口列表的RustScan扫描
        """
        try:
            cmd = self.rustscan_manager.get_command_args(
                target.ip,
                timeout=self.config.rustscan_timeout,
                batch_size=self.config.rustscan_batch_size,
                tries=self.config.rustscan_tries,
                ulimit=self.config.rustscan_ulimit,
                ports=ports
            )
        except FileNotFoundError as e:
            logger.error(f"构建RustScan命令失败: {e}")
            raise
        
        logger.info(f"💨 RustScan极速配置: timeout={self.config.rustscan_timeout}ms, batch={self.config.rustscan_batch_size}")
        
        # 安全的命令调试输出
        if len(ports) > 100:
            logger.debug(f"执行RustScan命令 (包含{len(ports)}个端口): rustscan -a {target.ip} ... -p [端口列表...]")
        else:
            logger.debug(f"执行RustScan命令: {' '.join(cmd)}")
        
        # 执行命令
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            error_msg = stderr.decode().strip()
            logger.error(f"RustScan执行失败: {error_msg}")
            return []
        
        # 解析greppable输出
        return self._parse_rustscan_greppable_output(stdout.decode())
    
    def _parse_rustscan_greppable_output(self, output: str) -> List[int]:
        """
        解析RustScan greppable输出
        
        Args:
            output: RustScan greppable输出文本
            
        Returns:
            List[int]: 端口列表
        """
        ports = []
        
        # greppable格式: ip -> [port1,port2,...]
        for line in output.strip().split('\n'):
            line = line.strip()
            if '->' in line and '[' in line and ']' in line:
                try:
                    # 提取方括号内的端口列表
                    bracket_content = line.split('[')[1].split(']')[0]
                    # 解析端口列表
                    port_strs = bracket_content.split(',')
                    for port_str in port_strs:
                        port_str = port_str.strip()
                        if port_str:
                            ports.append(int(port_str))
                except (ValueError, IndexError):
                    continue
        
        return sorted(list(set(ports)))  # 去重并排序
    
    async def _socket_scan_ports(self, target: ScanTarget) -> List[int]:
        """
        使用Python socket进行端口扫描（RustScan的备选方案）
        
        Args:
            target: 扫描目标
            
        Returns:
            List[int]: 开放端口列表
        """
        try:
            # 确定要扫描的端口
            if target.ports:
                ports_to_scan = target.ports
            else:
                # 使用配置中的预设端口列表
                ports_to_scan = self._get_preset_ports()
            
            logger.debug(f"开始socket扫描，目标端口数: {len(ports_to_scan)}")
            
            # 并发扫描端口
            semaphore = asyncio.Semaphore(50)  # 限制并发数
            tasks = []
            
            for port in ports_to_scan:
                task = asyncio.create_task(self._check_port_socket(target.ip, port, semaphore))
                tasks.append(task)
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 收集开放端口
            open_ports = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.debug(f"端口 {ports_to_scan[i]} 检查失败: {result}")
                elif result:
                    open_ports.append(ports_to_scan[i])
            
            logger.debug(f"Socket扫描完成，发现 {len(open_ports)} 个开放端口")
            return open_ports
            
        except Exception as e:
            logger.error(f"Socket扫描失败: {e}")
            return []
    
    def _get_preset_ports(self) -> List[int]:
        """
        获取预设端口列表，合并RustScan端口范围和配置中的preset_ports
        
        Returns:
            List[int]: 合并后的端口列表
        """
        # 解析RustScan端口范围
        rustscan_ports = []
        try:
            port_range = self.config.rustscan_ports
            if '-' in port_range:
                start, end = map(int, port_range.split('-'))
                rustscan_ports = list(range(start, end + 1))
            else:
                # 如果不是范围，可能是单个端口或逗号分隔的端口列表
                rustscan_ports = [int(p.strip()) for p in port_range.split(',')]
        except (ValueError, AttributeError) as e:
            logger.warning(f"解析RustScan端口范围失败: {e}，使用默认21-1000")
            rustscan_ports = list(range(21, 1001))
        
        # 合并RustScan端口和预设端口
        all_ports = set(rustscan_ports)
        all_ports.update(self.config.preset_ports)
        
        # 排序并返回
        final_ports = sorted(list(all_ports))
        
        logger.debug(f"预设端口合并: RustScan({len(rustscan_ports)}) + 预设({len(self.config.preset_ports)}) = 总计({len(final_ports)})")
        
        return final_ports
    
    async def _check_port_socket(self, ip: str, port: int, semaphore: asyncio.Semaphore) -> bool:
        """
        使用socket检查单个端口是否开放
        
        Args:
            ip: 目标IP
            port: 端口号
            semaphore: 并发控制信号量
            
        Returns:
            bool: 端口是否开放
        """
        async with semaphore:
            try:
                # 创建socket连接测试
                future = asyncio.open_connection(ip, port)
                reader, writer = await asyncio.wait_for(future, timeout=3.0)
                
                # 连接成功，端口开放
                writer.close()
                await writer.wait_closed()
                return True
                
            except (asyncio.TimeoutError, ConnectionRefusedError, OSError):
                # 连接失败，端口关闭
                return False
            except Exception as e:
                logger.debug(f"检查端口 {ip}:{port} 时发生异常: {e}")
                return False
    
    async def _grab_banners(self, ip: str, ports: List[int], progress_callback: Optional[callable] = None) -> List[PortInfo]:
        """
        收集端口Banner信息
        
        Args:
            ip: 目标IP
            ports: 端口列表
            progress_callback: 进度回调函数
            
        Returns:
            List[PortInfo]: 端口信息列表
        """
        port_infos = []
        
        # 并发获取Banner信息
        semaphore = asyncio.Semaphore(20)  # 限制并发数
        tasks = []
        
        for port in ports:
            task = asyncio.create_task(self._grab_single_banner(ip, port))
            tasks.append(task)
        
        # 逐个等待并显示进度
        completed = 0
        for i, task in enumerate(asyncio.as_completed(tasks)):
            try:
                result = await task
                port_infos.append(result)
                completed += 1
                
                if progress_callback:
                    await progress_callback("Banner抓取", f"正在获取服务信息... ({completed}/{len(ports)}) - 端口 {result.port}")
                    
            except Exception as e:
                logger.debug(f"获取端口 {ports[i]} Banner失败: {e}")
                # 创建基础端口信息
                port_infos.append(PortInfo(
                    port=ports[i],
                    state="open",
                    protocol=ServiceProtocol.TCP,
                    service=self._identify_service_by_port(ports[i])
                ))
                completed += 1
                
                if progress_callback:
                    await progress_callback("Banner抓取", f"正在获取服务信息... ({completed}/{len(ports)}) - 端口 {ports[i]} (failed)")
        
        return port_infos
    
    async def _grab_single_banner(self, ip: str, port: int) -> PortInfo:
        """
        获取单个端口的Banner信息
        
        Args:
            ip: 目标IP
            port: 端口号
            
        Returns:
            PortInfo: 端口信息
        """
        # 获取Banner
        banner = await self._get_banner(ip, port)
        
        # 识别服务
        service_info = self._identify_service(port, banner)
        
        # 创建端口信息
        port_info = PortInfo(
            port=port,
            state="open",
            protocol=ServiceProtocol.TCP,
            service=service_info.get("service", "unknown"),
            version=service_info.get("version"),
            banner=banner,
            confidence=service_info.get("confidence", 0.5)
        )
        
        return port_info
    
    async def _get_banner(self, ip: str, port: int, timeout: float = 5.0) -> Optional[str]:
        """
        获取端口Banner信息
        
        Args:
            ip: 目标IP
            port: 端口号
            timeout: 超时时间
            
        Returns:
            Optional[str]: Banner信息
        """
        try:
            # 创建连接
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(ip, port),
                timeout=timeout
            )
            
            # 尝试读取Banner
            try:
                # 等待服务器主动发送Banner
                banner_data = await asyncio.wait_for(reader.read(1024), timeout=2.0)
                if banner_data:
                    banner = banner_data.decode('utf-8', errors='ignore').strip()
                    if banner:
                        return banner
            except asyncio.TimeoutError:
                pass
            
            # 如果没有主动Banner，尝试发送HTTP请求
            if port in [80, 8080, 8000, 8001, 8008, 8081, 8082, 8888, 9000, 9090, 9999]:
                writer.write(b"GET / HTTP/1.1\r\nHost: " + ip.encode() + b"\r\n\r\n")
                await writer.drain()
                
                response_data = await asyncio.wait_for(reader.read(1024), timeout=3.0)
                if response_data:
                    response = response_data.decode('utf-8', errors='ignore').strip()
                    if response:
                        return response
            
            # 关闭连接
            writer.close()
            await writer.wait_closed()
            
            return None
            
        except Exception as e:
            logger.debug(f"获取Banner失败 {ip}:{port}: {e}")
            return None
    
    def _identify_service(self, port: int, banner: str) -> Dict[str, Any]:
        """
        基于端口号和Banner识别服务
        
        Args:
            port: 端口号
            banner: Banner信息
            
        Returns:
            Dict[str, Any]: 服务信息
        """
        # 首先基于端口号识别
        service_info = self._identify_by_port(port)
        
        # 然后基于Banner改进识别
        if banner:
            banner_lower = banner.lower()
            
            # HTTP服务检测
            if any(keyword in banner_lower for keyword in ["http/", "server:", "apache", "nginx", "iis"]):
                service_info["name"] = "http"
                # 提取服务器信息
                if "server:" in banner_lower:
                    server_match = re.search(r"server:\s*([^\r\n]+)", banner_lower)
                    if server_match:
                        service_info["version"] = server_match.group(1).strip()
            
            # SSH服务检测
            elif "ssh-" in banner_lower:
                service_info["name"] = "ssh"
                ssh_match = re.search(r"ssh-[\d\.]+", banner_lower)
                if ssh_match:
                    service_info["version"] = ssh_match.group(0)
            
            # FTP服务检测
            elif any(keyword in banner_lower for keyword in ["ftp", "220 "]):
                service_info["name"] = "ftp"
            
            # SMTP服务检测
            elif "220 " in banner and any(keyword in banner_lower for keyword in ["smtp", "mail"]):
                service_info["name"] = "smtp"
            
            # 恶意软件检测
            elif "morte c2" in banner_lower:
                service_info["name"] = "morte-c2"
                service_info["threat"] = "C2服务器"
            elif "usoppgo" in banner_lower or "king of snipers" in banner_lower:
                service_info["name"] = "usoppgo-ftp"
                service_info["threat"] = "可疑FTP服务"
            elif "cobaltstrike" in banner_lower or "beacon" in banner_lower:
                service_info["name"] = "cobaltstrike"
                service_info["threat"] = "CobaltStrike"
        
        return service_info
    
    def _identify_service_by_port(self, port: int) -> str:
        """
        仅基于端口号识别服务
        
        Args:
            port: 端口号
            
        Returns:
            str: 服务名称
        """
        return self._identify_by_port(port).get("name", "unknown")
    
    def _identify_by_port(self, port: int) -> Dict[str, Any]:
        """
        基于端口号识别服务
        
        Args:
            port: 端口号
            
        Returns:
            Dict[str, Any]: 服务信息
        """
        port_service_map = {
            # 常规服务
            21: {"name": "ftp", "description": "File Transfer Protocol"},
            22: {"name": "ssh", "description": "Secure Shell"},
            23: {"name": "telnet", "description": "Telnet"},
            25: {"name": "smtp", "description": "Simple Mail Transfer Protocol"},
            53: {"name": "dns", "description": "Domain Name System"},
            80: {"name": "http", "description": "HyperText Transfer Protocol"},
            110: {"name": "pop3", "description": "Post Office Protocol v3"},
            135: {"name": "msrpc", "description": "Microsoft RPC"},
            139: {"name": "netbios-ssn", "description": "NetBIOS Session Service"},
            143: {"name": "imap", "description": "Internet Message Access Protocol"},
            443: {"name": "https", "description": "HTTP Secure"},
            445: {"name": "smb", "description": "Server Message Block"},
            993: {"name": "imaps", "description": "IMAP Secure"},
            995: {"name": "pop3s", "description": "POP3 Secure"},
            1433: {"name": "mssql", "description": "Microsoft SQL Server"},
            3306: {"name": "mysql", "description": "MySQL Database"},
            3389: {"name": "rdp", "description": "Remote Desktop Protocol"},
            5432: {"name": "postgresql", "description": "PostgreSQL Database"},
            6379: {"name": "redis", "description": "Redis Database"},
            27017: {"name": "mongodb", "description": "MongoDB Database"},
            
            # VPN端口
            1194: {"name": "openvpn", "description": "OpenVPN", "category": "vpn"},
            1723: {"name": "pptp", "description": "PPTP VPN", "category": "vpn"},
            4500: {"name": "ipsec", "description": "IPSec VPN", "category": "vpn"},
            51820: {"name": "wireguard", "description": "WireGuard VPN", "category": "vpn"},
            500: {"name": "ike", "description": "IKE (IPSec)", "category": "vpn"},
            
            # VNC端口
            5800: {"name": "vnc-http", "description": "VNC HTTP", "category": "remote"},
            5900: {"name": "vnc", "description": "Virtual Network Computing", "category": "remote"},
            5901: {"name": "vnc", "description": "VNC Display 1", "category": "remote"},
            5902: {"name": "vnc", "description": "VNC Display 2", "category": "remote"},
            5903: {"name": "vnc", "description": "VNC Display 3", "category": "remote"},
            5904: {"name": "vnc", "description": "VNC Display 4", "category": "remote"},
            5905: {"name": "vnc", "description": "VNC Display 5", "category": "remote"},
            
            # 远程管理工具
            6568: {"name": "anydesk", "description": "AnyDesk Remote Desktop", "category": "remote"},
            5938: {"name": "teamviewer", "description": "TeamViewer", "category": "remote"},
            6129: {"name": "dameware", "description": "DameWare Remote Control", "category": "remote"},
            8200: {"name": "gotomypc", "description": "GoToMyPC", "category": "remote"},
            
            # 恶意软件和后门端口
            666: {"name": "malware", "description": "多种恶意软件", "category": "malware", "threat": "高"},
            1080: {"name": "socks-proxy", "description": "SOCKS代理/恶意软件", "category": "proxy", "threat": "中"},
            1234: {"name": "ultors-trojan", "description": "Ultors Trojan", "category": "malware", "threat": "高"},
            1243: {"name": "subseven", "description": "SubSeven Backdoor", "category": "malware", "threat": "高"},
            1337: {"name": "hacker-tools", "description": "Empire/CrackMapExec等黑客工具", "category": "malware", "threat": "高"},
            2222: {"name": "c2-channel", "description": "DoHC2/ExternalC2/Qakbot C2", "category": "malware", "threat": "高"},
            3000: {"name": "beef-panel", "description": "BeEF项目HTTP面板", "category": "malware", "threat": "中"},
            4444: {"name": "metasploit", "description": "Metasploit默认监听端口", "category": "malware", "threat": "高"},
            6666: {"name": "irc-botnet", "description": "IRC僵尸网络", "category": "malware", "threat": "高"},
            6667: {"name": "irc", "description": "IRC (可能是僵尸网络)", "category": "irc", "threat": "中"},
            8080: {"name": "http-proxy", "description": "HTTP代理/多种恶意软件", "category": "proxy", "threat": "中"},
            9050: {"name": "tor-socks", "description": "Tor SOCKS代理", "category": "proxy", "threat": "中"},
            12345: {"name": "netbus", "description": "NetBus Trojan", "category": "malware", "threat": "高"},
            31337: {"name": "elite-tools", "description": "SliverC2/Back Orifice", "category": "malware", "threat": "高"},
            50050: {"name": "cobaltstrike", "description": "CobaltStrike TeamServer", "category": "malware", "threat": "高"},
        }
        
        return port_service_map.get(port, {"name": "unknown", "description": f"未知服务 (端口 {port})"})


async def test_scanner():
    """测试扫描器功能"""
    config = ScanConfig()
    scanner = PortScanner(config)
    
    # 测试目标
    target = ScanTarget(ip="127.0.0.1")
    
    try:
        result = await scanner.scan_target(target)
        print(f"扫描结果: {len(result)} 个开放端口")
        for port_info in result:
            print(f"  端口 {port_info.port}: {port_info.service}")
            if port_info.banner:
                print(f"    Banner: {port_info.banner[:100]}...")
    except Exception as e:
        print(f"扫描失败: {e}")


if __name__ == "__main__":
    asyncio.run(test_scanner()) 