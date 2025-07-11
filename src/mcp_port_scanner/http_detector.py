"""
第二层：基于Banner的智能HTTP服务识别
"""

import asyncio
import re
from typing import List, Dict, Any, Optional, Tuple
import httpx
from loguru import logger
from urllib.parse import urlparse, urljoin
import time

from .models import PortInfo, HTTPInfo, ScanConfig, HTTPDetectionRule


class HTTPDetector:
    """HTTP服务检测器 - 第二层检测功能"""
    
    def __init__(self, config: Optional[ScanConfig] = None):
        self.config = config or ScanConfig()
        self.detection_rules = self._load_detection_rules()
        self._setup_logging()
    
    def _setup_logging(self) -> None:
        """设置日志"""
        if self.config.enable_logging:
            logger.add(
                "logs/http_detector_{time}.log",
                level=self.config.log_level,
                rotation="1 day",
                retention="7 days"
            )
    
    def _load_detection_rules(self) -> List[HTTPDetectionRule]:
        """
        加载HTTP检测规则
        
        Returns:
            List[HTTPDetectionRule]: HTTP检测规则列表
        """
        rules = [
            HTTPDetectionRule(
                name="Standard HTTP Response",
                description="标准HTTP响应特征",
                banner_patterns=[
                    r"HTTP/\d\.\d",
                    r"200 OK",
                    r"404 Not Found",
                    r"500 Internal Server Error"
                ],
                port_hints=[80, 443, 8080, 8443],
                confidence_boost=0.3,
                priority=1
            ),
            HTTPDetectionRule(
                name="Server Header",
                description="HTTP Server头部信息",
                banner_patterns=[
                    r"Server:\s*(nginx|apache|iis|tomcat|jetty)",
                    r"Server:\s*Microsoft-IIS",
                    r"Server:\s*Apache",
                    r"Server:\s*nginx"
                ],
                port_hints=[],
                confidence_boost=0.4,
                priority=1
            ),
            HTTPDetectionRule(
                name="Content-Type Header",
                description="HTTP Content-Type头部",
                banner_patterns=[
                    r"Content-Type:\s*text/html",
                    r"Content-Type:\s*application/json",
                    r"Content-Type:\s*text/plain"
                ],
                port_hints=[],
                confidence_boost=0.2,
                priority=2
            ),
            HTTPDetectionRule(
                name="Web Application Servers",
                description="Web应用服务器特征",
                banner_patterns=[
                    r"Jetty",
                    r"Tomcat",
                    r"WebLogic",
                    r"WebSphere",
                    r"JBoss",
                    r"Undertow"
                ],
                port_hints=[8080, 8443, 9080, 9443],
                confidence_boost=0.3,
                priority=1
            ),
            HTTPDetectionRule(
                name="Reverse Proxy",
                description="反向代理服务器",
                banner_patterns=[
                    r"Via:\s*",
                    r"X-Forwarded-For:",
                    r"X-Real-IP:",
                    r"CloudFlare",
                    r"X-Served-By:"
                ],
                port_hints=[80, 443],
                confidence_boost=0.2,
                priority=2
            ),
            HTTPDetectionRule(
                name="Non-Standard HTTP Ports",
                description="非标准端口的HTTP服务",
                banner_patterns=[
                    r"HTTP/\d\.\d"
                ],
                port_hints=[3000, 4000, 5000, 8000, 8081, 8082, 9000, 9090],
                confidence_boost=0.4,
                priority=1
            )
        ]
        
        return sorted(rules, key=lambda x: x.priority)
    
    async def detect_http_services(self, ip: str, port_infos: List[PortInfo]) -> List[HTTPInfo]:
        """
        检测HTTP服务
        
        Args:
            ip: 目标IP
            port_infos: 端口信息列表
            
        Returns:
            List[HTTPInfo]: HTTP服务信息列表
        """
        logger.info(f"开始检测 {ip} 的HTTP服务")
        
        # 第一步：基于Banner和规则识别可能的HTTP端口
        http_candidates = self._identify_http_candidates(port_infos)
        
        if not http_candidates:
            logger.info(f"未发现 {ip} 的HTTP服务候选端口")
            return []
        
        logger.info(f"发现 {len(http_candidates)} 个HTTP候选端口: {[p.port for p in http_candidates]}")
        
        # 第二步：验证HTTP服务并获取详细信息
        http_services = await self._verify_http_services(ip, http_candidates)
        
        logger.info(f"确认 {len(http_services)} 个HTTP服务")
        return http_services
    
    def _identify_http_candidates(self, port_infos: List[PortInfo]) -> List[PortInfo]:
        """
        基于Banner和规则识别HTTP候选端口
        
        Args:
            port_infos: 端口信息列表
            
        Returns:
            List[PortInfo]: HTTP候选端口列表
        """
        candidates = []
        
        for port_info in port_infos:
            confidence_score = 0.0
            matched_rules = []
            
            # 基础服务识别已经标记为HTTP的端口
            if port_info.service in ['http', 'https', 'http-alt', 'https-alt']:
                confidence_score += 0.5
                matched_rules.append("Service identification")
            
            # 应用检测规则
            for rule in self.detection_rules:
                rule_score = self._apply_detection_rule(port_info, rule)
                if rule_score > 0:
                    confidence_score += rule_score
                    matched_rules.append(rule.name)
            
            # 如果置信度超过阈值，则认为是HTTP候选
            if confidence_score >= 0.3:
                port_info.confidence = min(confidence_score, 1.0)
                logger.debug(f"端口 {port_info.port} HTTP置信度: {confidence_score:.2f}, "
                           f"匹配规则: {matched_rules}")
                candidates.append(port_info)
        
        return candidates
    
    def _apply_detection_rule(self, port_info: PortInfo, rule: HTTPDetectionRule) -> float:
        """
        应用单个检测规则
        
        Args:
            port_info: 端口信息
            rule: 检测规则
            
        Returns:
            float: 规则匹配得分
        """
        score = 0.0
        
        # 检查端口提示
        if port_info.port in rule.port_hints:
            score += 0.1
        
        # 检查Banner模式
        if port_info.banner:
            for pattern in rule.banner_patterns:
                if re.search(pattern, port_info.banner, re.IGNORECASE):
                    score += rule.confidence_boost
                    break
        
        return score
    
    async def _verify_http_services(self, ip: str, candidates: List[PortInfo]) -> List[HTTPInfo]:
        """
        验证HTTP服务并获取详细信息
        
        Args:
            ip: 目标IP
            candidates: HTTP候选端口列表
            
        Returns:
            List[HTTPInfo]: 验证成功的HTTP服务列表
        """
        http_services = []
        
        # 并发验证所有候选端口
        tasks = []
        for port_info in candidates:
            task = asyncio.create_task(self._verify_single_http_service(ip, port_info))
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.warning(f"验证HTTP服务失败 {ip}:{candidates[i].port}: {result}")
            elif result:
                http_services.append(result)
        
        return http_services
    
    async def _verify_single_http_service(self, ip: str, port_info: PortInfo) -> Optional[HTTPInfo]:
        """
        验证单个HTTP服务
        
        Args:
            ip: 目标IP
            port_info: 端口信息
            
        Returns:
            Optional[HTTPInfo]: HTTP服务信息，如果验证失败则返回None
        """
        # 尝试HTTP和HTTPS
        protocols = []
        
        # 根据端口和Banner决定协议优先级
        if port_info.port in [443, 8443] or 'ssl' in (port_info.banner or '').lower():
            protocols = ['https', 'http']
        else:
            protocols = ['http', 'https']
        
        for protocol in protocols:
            url = f"{protocol}://{ip}:{port_info.port}/"
            
            try:
                http_info = await self._probe_http_service(url, port_info)
                if http_info:
                    return http_info
            except Exception as e:
                logger.debug(f"HTTP探测失败 {url}: {e}")
                continue
        
        return None
    
    async def _probe_http_service(self, url: str, port_info: PortInfo) -> Optional[HTTPInfo]:
        """
        探测HTTP服务详细信息
        
        Args:
            url: HTTP URL
            port_info: 端口信息
            
        Returns:
            Optional[HTTPInfo]: HTTP服务信息
        """
        start_time = time.time()
        
        timeout = httpx.Timeout(
            connect=self.config.http_timeout,
            read=self.config.http_timeout,
            write=self.config.http_timeout,
            pool=self.config.http_timeout
        )
        
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=False,
            verify=False  # 忽略SSL证书验证
        ) as client:
            try:
                response = await client.get(
                    url,
                    headers={
                        'User-Agent': self.config.http_user_agent,
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
                    }
                )
                
                response_time = time.time() - start_time
                
                # 创建HTTP信息对象
                http_info = HTTPInfo(
                    url=url,
                    status_code=response.status_code,
                    headers=dict(response.headers),
                    is_https=url.startswith('https'),
                    response_time=response_time
                )
                
                # 提取服务器信息
                if 'server' in response.headers:
                    http_info.server = response.headers['server']
                
                # 提取内容长度
                if 'content-length' in response.headers:
                    try:
                        http_info.content_length = int(response.headers['content-length'])
                    except ValueError:
                        pass
                
                # 处理重定向
                if 300 <= response.status_code < 400 and 'location' in response.headers:
                    http_info.redirect_url = response.headers['location']
                
                # 如果状态码是200，获取页面内容信息
                if response.status_code == 200:
                    try:
                        content = response.text
                        http_info.title = self._extract_title(content)
                        # 移除技术栈识别功能
                        # http_info.technologies = self._identify_technologies(content, response.headers)
                    except Exception as e:
                        logger.debug(f"解析页面内容失败: {e}")
                
                logger.debug(f"HTTP探测成功: {url} (状态码: {response.status_code})")
                return http_info
                
            except httpx.TimeoutException:
                logger.debug(f"HTTP请求超时: {url}")
            except httpx.ConnectError:
                logger.debug(f"HTTP连接失败: {url}")
            except Exception as e:
                logger.debug(f"HTTP请求异常: {url}, {e}")
        
        return None
    
    def _extract_title(self, content: str) -> Optional[str]:
        """
        提取页面标题
        
        Args:
            content: 页面内容
            
        Returns:
            Optional[str]: 页面标题
        """
        try:
            title_match = re.search(r'<title[^>]*>(.*?)</title>', content, re.IGNORECASE | re.DOTALL)
            if title_match:
                title = title_match.group(1).strip()
                # 清理标题内容
                title = re.sub(r'\s+', ' ', title)
                return title[:200]  # 限制标题长度
        except Exception:
            pass
        
        return None
    
    def _identify_technologies(self, content: str, headers: Dict[str, str]) -> List[str]:
        """
        识别Web技术栈 (已禁用)
        
        Args:
            content: 页面内容
            headers: HTTP头部
            
        Returns:
            List[str]: 技术栈列表
        """
        # 技术栈识别功能已被移除
        return []


# 测试函数
async def test_http_detector():
    """测试HTTP检测器"""
    from .scanner import PortScanner
    from .models import ScanTarget
    
    # 创建测试端口信息
    port_infos = [
        PortInfo(
            port=80,
            protocol="tcp",
            state="open",
            service="http",
            banner="HTTP/1.1 200 OK\r\nServer: nginx/1.18.0\r\n"
        ),
        PortInfo(
            port=8080,
            protocol="tcp",
            state="open",
            banner="HTTP/1.1 200 OK\r\nServer: Apache-Coyote/1.1\r\n"
        ),
        PortInfo(
            port=22,
            protocol="tcp",
            state="open",
            service="ssh",
            banner="SSH-2.0-OpenSSH_8.2p1"
        )
    ]
    
    detector = HTTPDetector()
    http_services = await detector.detect_http_services("127.0.0.1", port_infos)
    
    print(f"检测到 {len(http_services)} 个HTTP服务:")
    for service in http_services:
        print(f"  {service.url} - {service.title} ({service.server})")


if __name__ == "__main__":
    asyncio.run(test_http_detector()) 