"""
第三层：HTTP服务深度探测和管理目录扫描
"""

import asyncio
from typing import List, Dict, Any, Optional, Set
import httpx
from loguru import logger
from urllib.parse import urljoin, urlparse
import time
import re

from .models import HTTPInfo, DirectoryInfo, ScanConfig, AdminDirectoryRule


class WebProber:
    """Web深度探测器 - 第三层探测功能"""
    
    def __init__(self, config: Optional[ScanConfig] = None):
        self.config = config or ScanConfig()
        self.admin_rules = self._load_admin_directory_rules()
        self._setup_logging()
    
    def _setup_logging(self) -> None:
        """设置日志"""
        if self.config.enable_logging:
            logger.add(
                "logs/web_prober_{time}.log",
                level=self.config.log_level,
                rotation="1 day",
                retention="7 days"
            )
    
    def _load_admin_directory_rules(self) -> List[AdminDirectoryRule]:
        """
        加载管理目录扫描规则
        
        Returns:
            List[AdminDirectoryRule]: 管理目录规则列表
        """
        rules = [
            AdminDirectoryRule(
                technology="Generic",
                paths=[
                    "/admin", "/admin/", "/administrator", "/administrator/",
                    "/manage", "/manage/", "/management", "/management/",
                    "/panel", "/panel/", "/control", "/control/",
                    "/backend", "/backend/", "/dashboard", "/dashboard/",
                    "/login", "/login.php", "/login.html", "/login.jsp",
                    "/admin.php", "/admin.html", "/admin.jsp",
                    "/wp-admin", "/wp-admin/", "/wp-login.php",
                    "/phpmyadmin", "/phpmyadmin/", "/pma/",
                    "/adminer", "/adminer.php"
                ],
                indicators=[],
                priority=1
            ),
            AdminDirectoryRule(
                technology="Apache Tomcat",
                paths=[
                    "/manager", "/manager/", "/manager/html",
                    "/host-manager", "/host-manager/",
                    "/admin", "/admin/", "/admin/index.jsp"
                ],
                indicators=["tomcat", "apache-coyote", "catalina"],
                priority=1
            ),
            AdminDirectoryRule(
                technology="JBoss",
                paths=[
                    "/admin-console", "/admin-console/",
                    "/jmx-console", "/jmx-console/",
                    "/web-console", "/web-console/",
                    "/status", "/status/"
                ],
                indicators=["jboss", "wildfly"],
                priority=1
            ),
            AdminDirectoryRule(
                technology="WebLogic",
                paths=[
                    "/console", "/console/",
                    "/em", "/em/",
                    "/wls-exporter", "/wls-exporter/"
                ],
                indicators=["weblogic"],
                priority=1
            ),
            AdminDirectoryRule(
                technology="Nginx",
                paths=[
                    "/nginx_status", "/status",
                    "/server-status", "/server-info"
                ],
                indicators=["nginx"],
                priority=2
            ),
            AdminDirectoryRule(
                technology="Apache",
                paths=[
                    "/server-status", "/server-info",
                    "/server-statistics", "/status"
                ],
                indicators=["apache"],
                priority=2
            ),
            AdminDirectoryRule(
                technology="PHP",
                paths=[
                    "/phpinfo.php", "/info.php", "/test.php",
                    "/phpmyadmin", "/phpmyadmin/",
                    "/adminer.php", "/db.php"
                ],
                indicators=["php", "x-powered-by: php"],
                priority=1
            ),
            AdminDirectoryRule(
                technology="WordPress",
                paths=[
                    "/wp-admin", "/wp-admin/", "/wp-login.php",
                    "/wp-content/", "/wp-includes/",
                    "/xmlrpc.php", "/readme.html"
                ],
                indicators=["wordpress", "wp-content", "wp-includes"],
                priority=1
            ),
            AdminDirectoryRule(
                technology="Jenkins",
                paths=[
                    "/", "/login", "/manage", "/configure",
                    "/script", "/systemInfo", "/asynchPeople"
                ],
                indicators=["jenkins", "hudson"],
                priority=1
            ),
            AdminDirectoryRule(
                technology="GitLab",
                paths=[
                    "/admin", "/admin/", "/users/sign_in",
                    "/explore", "/help", "/api/v4"
                ],
                indicators=["gitlab"],
                priority=1
            ),
            AdminDirectoryRule(
                technology="Grafana",
                paths=[
                    "/login", "/admin", "/api/health",
                    "/api/admin/stats", "/public/build/"
                ],
                indicators=["grafana"],
                priority=1
            ),
            AdminDirectoryRule(
                technology="Elastic",
                paths=[
                    "/", "/_cluster/health", "/_cat/nodes",
                    "/_plugin/head/", "/app/kibana"
                ],
                indicators=["elasticsearch", "kibana", "elastic"],
                priority=1
            ),
            AdminDirectoryRule(
                technology="API Endpoints",
                paths=[
                    "/api", "/api/", "/api/v1", "/api/v2",
                    "/rest", "/rest/", "/graphql",
                    "/swagger", "/swagger-ui", "/docs",
                    "/openapi.json", "/api-docs"
                ],
                indicators=["api", "rest", "json"],
                priority=2
            ),
            AdminDirectoryRule(
                technology="Backup Files",
                paths=[
                    "/backup", "/backup/", "/backups", "/backups/",
                    "/dump", "/dump/", "/export", "/export/",
                    "/backup.sql", "/dump.sql", "/database.sql",
                    "/config.bak", "/web.config.bak"
                ],
                indicators=[],
                priority=3
            )
        ]
        
        return sorted(rules, key=lambda x: x.priority)
    
    async def probe_web_services(self, http_services: List[HTTPInfo]) -> List[DirectoryInfo]:
        """
        对HTTP服务进行深度探测
        
        Args:
            http_services: HTTP服务列表
            
        Returns:
            List[DirectoryInfo]: 发现的目录信息列表
        """
        if not self.config.admin_scan_enabled:
            logger.info("管理目录扫描已禁用")
            return []
        
        logger.info(f"开始深度探测 {len(http_services)} 个HTTP服务")
        
        all_directories = []
        
        # 并发探测所有HTTP服务
        semaphore = asyncio.Semaphore(self.config.admin_scan_threads)
        tasks = []
        
        for http_service in http_services:
            task = asyncio.create_task(
                self._probe_single_service(http_service, semaphore)
            )
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.warning(f"探测服务失败 {http_services[i].url}: {result}")
            else:
                all_directories.extend(result)
        
        logger.info(f"深度探测完成，发现 {len(all_directories)} 个目录")
        return all_directories
    
    async def _probe_single_service(self, http_service: HTTPInfo, semaphore: asyncio.Semaphore) -> List[DirectoryInfo]:
        """
        探测单个HTTP服务
        
        Args:
            http_service: HTTP服务信息
            semaphore: 并发控制信号量
            
        Returns:
            List[DirectoryInfo]: 发现的目录列表
        """
        async with semaphore:
            logger.debug(f"开始探测服务: {http_service.url}")
            
            # 选择适用的扫描规则
            applicable_rules = self._select_applicable_rules(http_service)
            
            # 收集所有要扫描的路径
            paths_to_scan = set()
            for rule in applicable_rules:
                paths_to_scan.update(rule.paths)
            
            # 执行目录扫描
            directories = await self._scan_directories(http_service.url, list(paths_to_scan))
            
            logger.debug(f"服务 {http_service.url} 探测完成，发现 {len(directories)} 个目录")
            return directories
    
    def _select_applicable_rules(self, http_service: HTTPInfo) -> List[AdminDirectoryRule]:
        """
        选择适用的扫描规则
        
        Args:
            http_service: HTTP服务信息
            
        Returns:
            List[AdminDirectoryRule]: 适用的规则列表
        """
        applicable_rules = []
        
        # 获取服务信息用于匹配
        service_info = {
            'server': (http_service.server or '').lower(),
            'technologies': [tech.lower() for tech in http_service.technologies],
            'title': (http_service.title or '').lower(),
            'headers': {k.lower(): v.lower() for k, v in http_service.headers.items()}
        }
        
        for rule in self.admin_rules:
            # 通用规则始终适用
            if rule.technology == "Generic":
                applicable_rules.append(rule)
                continue
            
            # 检查规则指示器是否匹配
            rule_matches = False
            
            for indicator in rule.indicators:
                indicator_lower = indicator.lower()
                
                # 检查服务器头部
                if indicator_lower in service_info['server']:
                    rule_matches = True
                    break
                
                # 检查技术栈
                if indicator_lower in service_info['technologies']:
                    rule_matches = True
                    break
                
                # 检查页面标题
                if indicator_lower in service_info['title']:
                    rule_matches = True
                    break
                
                # 检查HTTP头部
                for header_value in service_info['headers'].values():
                    if indicator_lower in header_value:
                        rule_matches = True
                        break
                
                if rule_matches:
                    break
            
            if rule_matches:
                applicable_rules.append(rule)
                logger.debug(f"规则匹配: {rule.technology} for {http_service.url}")
        
        return sorted(applicable_rules, key=lambda x: x.priority)
    
    async def _scan_directories(self, base_url: str, paths: List[str]) -> List[DirectoryInfo]:
        """
        扫描目录列表
        
        Args:
            base_url: 基础URL
            paths: 路径列表
            
        Returns:
            List[DirectoryInfo]: 目录信息列表
        """
        directories = []
        
        timeout = httpx.Timeout(
            connect=self.config.admin_scan_timeout,
            read=self.config.admin_scan_timeout,
            write=self.config.admin_scan_timeout,
            pool=self.config.admin_scan_timeout
        )
        
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=False,
            verify=False
        ) as client:
            
            # 并发扫描所有路径
            semaphore = asyncio.Semaphore(self.config.admin_scan_threads)
            tasks = []
            
            for path in paths:
                task = asyncio.create_task(
                    self._scan_single_directory(client, base_url, path, semaphore)
                )
                tasks.append(task)
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.debug(f"扫描目录失败 {base_url}{paths[i]}: {result}")
                elif result:
                    directories.append(result)
        
        return directories
    
    async def _scan_single_directory(self, client: httpx.AsyncClient, base_url: str, 
                                   path: str, semaphore: asyncio.Semaphore) -> Optional[DirectoryInfo]:
        """
        扫描单个目录
        
        Args:
            client: HTTP客户端
            base_url: 基础URL
            path: 目录路径
            semaphore: 并发控制信号量
            
        Returns:
            Optional[DirectoryInfo]: 目录信息，如果不存在则返回None
        """
        async with semaphore:
            url = urljoin(base_url, path)
            start_time = time.time()
            
            try:
                response = await client.get(
                    url,
                    headers={
                        'User-Agent': self.config.http_user_agent,
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
                    }
                )
                
                response_time = time.time() - start_time
                
                # 只记录有意义的响应
                if self._is_meaningful_response(response):
                    dir_info = DirectoryInfo(
                        path=path,
                        status_code=response.status_code,
                        response_time=response_time
                    )
                    
                    # 提取内容长度
                    if 'content-length' in response.headers:
                        try:
                            dir_info.content_length = int(response.headers['content-length'])
                        except ValueError:
                            pass
                    
                    # 提取内容类型
                    if 'content-type' in response.headers:
                        dir_info.content_type = response.headers['content-type']
                    
                    # 如果是200状态码，提取页面标题并判断是否为管理界面
                    if response.status_code == 200:
                        try:
                            content = response.text
                            dir_info.title = self._extract_title(content)
                            dir_info.is_admin = self._is_admin_interface(content, path)
                        except Exception as e:
                            logger.debug(f"解析页面内容失败: {e}")
                    
                    logger.debug(f"发现目录: {url} (状态码: {response.status_code})")
                    return dir_info
                
            except httpx.TimeoutException:
                logger.debug(f"目录扫描超时: {url}")
            except httpx.ConnectError:
                logger.debug(f"目录连接失败: {url}")
            except Exception as e:
                logger.debug(f"目录扫描异常: {url}, {e}")
        
        return None
    
    def _is_meaningful_response(self, response: httpx.Response) -> bool:
        """
        判断响应是否有意义
        
        Args:
            response: HTTP响应
            
        Returns:
            bool: 是否有意义
        """
        # 有意义的状态码
        meaningful_codes = {200, 201, 301, 302, 401, 403, 500, 503}
        
        if response.status_code not in meaningful_codes:
            return False
        
        # 检查内容长度，过滤明显的404页面
        content_length = response.headers.get('content-length')
        if content_length:
            try:
                length = int(content_length)
                # 过滤过小或过大的响应
                if length < 50 or length > 1024 * 1024:  # 50字节到1MB
                    return False
            except ValueError:
                pass
        
        return True
    
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
                title = re.sub(r'\s+', ' ', title)
                return title[:200]
        except Exception:
            pass
        
        return None
    
    def _is_admin_interface(self, content: str, path: str) -> bool:
        """
        判断是否为管理界面
        
        Args:
            content: 页面内容
            path: 路径
            
        Returns:
            bool: 是否为管理界面
        """
        content_lower = content.lower()
        path_lower = path.lower()
        
        # 基于路径的判断
        admin_path_keywords = [
            'admin', 'manage', 'control', 'panel', 'dashboard',
            'console', 'backend', 'login'
        ]
        
        for keyword in admin_path_keywords:
            if keyword in path_lower:
                return True
        
        # 基于内容的判断
        admin_content_keywords = [
            'administration', 'admin panel', 'control panel',
            'management console', 'dashboard', 'login',
            'username', 'password', 'sign in', 'log in',
            'administrative', 'manager', 'control'
        ]
        
        for keyword in admin_content_keywords:
            if keyword in content_lower:
                return True
        
        # 检查表单元素
        if re.search(r'<input[^>]*type=["\']password["\']', content_lower):
            return True
        
        if re.search(r'<form[^>]*action[^>]*login', content_lower):
            return True
        
        return False


# 测试函数
async def test_web_prober():
    """测试Web探测器"""
    from .models import HTTPInfo
    
    # 创建测试HTTP服务
    http_services = [
        HTTPInfo(
            url="http://127.0.0.1:8080/",
            status_code=200,
            title="Apache Tomcat",
            server="Apache-Coyote/1.1",
            technologies=["Tomcat"],
            headers={"server": "Apache-Coyote/1.1"}
        )
    ]
    
    prober = WebProber()
    directories = await prober.probe_web_services(http_services)
    
    print(f"发现 {len(directories)} 个目录:")
    for directory in directories:
        admin_flag = " [ADMIN]" if directory.is_admin else ""
        print(f"  {directory.path} - {directory.status_code}{admin_flag}")


if __name__ == "__main__":
    asyncio.run(test_web_prober()) 