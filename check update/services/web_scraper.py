import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import re
from typing import Dict, List, Optional
import logging
from urllib.parse import urljoin, urlparse
import time
import random
from collections import defaultdict
import urllib3
import uuid
import hashlib

# 禁用SSL警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 导入请求管理器和缓存
from services.request_manager import request_manager
from utils.page_cache import page_cache
from config.settings import PAGE_CACHE_TTL

# 导入配置
try:
    from config.anti_ban_config import AntiBanConfig
except ImportError:
    # 如果配置文件不存在，使用默认配置
    class AntiBanConfig:
        MIN_INTERVAL = 2
        MAX_INTERVAL = 15
        MAX_RETRIES = 5
        PROXY_POOL = [None]
        USER_AGENTS = ['Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36']

class WebScraper:
    def __init__(self):
        self.session = requests.Session()
        
        # 使用配置文件中的参数
        self.session.headers.update(AntiBanConfig.HEADERS)
        self.proxies = AntiBanConfig.PROXY_POOL
        self.user_agents = AntiBanConfig.USER_AGENTS
        
        self.current_proxy_index = 0
        
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)
        
        self.domain_stats = defaultdict(lambda: {'last_request': 0, 'current_interval': 1, 'consecutive_failures': 0})
        self.max_interval = AntiBanConfig.MAX_INTERVAL
        self.min_interval = AntiBanConfig.MIN_INTERVAL
        self.failure_penalty = AntiBanConfig.FAILURE_PENALTY
        self.domain_min_length = {
            'hsex.men': 300
        }
        
    def _setup_cookies(self):
        """设置更完整的浏览器Cookie模拟"""
        # 生成唯一的会话ID
        session_id = str(uuid.uuid4()).replace('-', '')[:26]
        cf_clearance = ''.join(random.choices('0123456789abcdef', k=43))
        cf_bm = ''.join(random.choices('0123456789abcdef', k=30))
        
        # 设置hsex.men相关的Cookie
        self.session.cookies.set('PHPSESSID', session_id, domain='hsex.men')
        self.session.cookies.set('cf_clearance', cf_clearance, domain='.hsex.men')
        self.session.cookies.set('__cf_bm', cf_bm, domain='.hsex.men')
        self.session.cookies.set('_ga', f'GA1.2.{random.randint(1000000000, 9999999999)}.{int(time.time())}', domain='.hsex.men')
        self.session.cookies.set('_gid', f'GA1.2.{random.randint(100000000, 999999999)}', domain='.hsex.men')
        self.session.cookies.set('_gat', '1', domain='.hsex.men')
        
        # 设置通用Cookie
        self.session.cookies.set('timezone', 'Asia/Shanghai')
        self.session.cookies.set('language', 'zh-CN')
        
    def _run_network_diagnosis(self, url: str):
        """运行网络诊断，帮助用户理解问题"""
        self.logger.info("🔍 正在运行快速网络诊断...")
        print("🔍 正在运行快速网络诊断...")
        print("=" * 50)
        
        # 测试基础网络连接
        try:
            import socket
            hostname = 'hsex.men'
            port = 443
            
            # DNS解析测试
            try:
                ip = socket.gethostbyname(hostname)
                print(f"✅ DNS解析成功: {hostname} -> {ip}")
            except socket.gaierror:
                print(f"❌ DNS解析失败: 无法解析 {hostname}")
                print("💡 建议: 检查网络连接或更换DNS服务器")
                return
                
            # 端口连接测试
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(5)
                result = sock.connect_ex((hostname, port))
                sock.close()
                
                if result == 0:
                    print(f"✅ 端口连接成功: {hostname}:{port}")
                else:
                    print(f"❌ 端口连接失败: {hostname}:{port} (错误码: {result})")
                    print("💡 建议: 检查防火墙设置或网络限制")
                    return
                    
            except Exception as e:
                print(f"❌ 端口测试异常: {str(e)}")
                
        except Exception as e:
            print(f"❌ 网络诊断异常: {str(e)}")
            
        # 代理状态检查（仅快速检查，不测试连接）
        working_proxies = []
        has_proxy = False
        for proxy in self.proxies:
            if proxy is None:
                working_proxies.append(proxy)
            else:
                has_proxy = True
                working_proxies.append(proxy)
        
        self.proxies = working_proxies if working_proxies else [None]
        
        print("\n📊 诊断结果:")
        if not has_proxy:
            print("📡 使用直连模式")
        else:
            print(f"✅ 配置了 {len([p for p in self.proxies if p])} 个代理")
            
        print("=" * 50)
        self.logger.info("✓ 网络诊断完成")

    def _get_domain(self, url: str) -> str:
        return urlparse(url).netloc

    def _adjust_interval(self, domain: str, success: bool):
        stats = self.domain_stats[domain]
        if success:
            stats['current_interval'] = max(self.min_interval, stats['current_interval'] * 0.5)
            stats['consecutive_failures'] = 0
        else:
            stats['consecutive_failures'] += 1
            penalty = self.failure_penalty ** min(stats['consecutive_failures'], 3)
            stats['current_interval'] = min(self.max_interval, stats['current_interval'] * penalty)

    def is_valid_html_for_domain(self, domain: str, html: str) -> bool:
        if domain.endswith('hsex.men'):
            patterns = [
                r'class=[\"\']?[^>]*col-xs-6\s+col-md-3',
                r'class=[\"\']?[^>]*thumbnail',
                r'class=[\"\']?[^>]*video-item',
                r'class=[\"\']?[^>]*item',
                r'class=[\"\']?[^>]*card',
                r'class=[\"\']?[^>]*video-card'
            ]
            for p in patterns:
                if re.search(p, html):
                    return True
        flags = [
            'cloudflare',
            'just a moment',
            'enable javascript',
            'checking your browser'
        ]
        low = html.lower()
        for f in flags:
            if f in low:
                return False
        return False

    def get_min_length_for_domain(self, domain: str) -> int:
        return self.domain_min_length.get(domain, 500)

    def get_page_content(self, url: str, max_retries: int = None, use_cache: bool = True) -> Optional[str]:
        """
        获取页面内容（支持缓存和智能重试）
        
        Args:
            url: 页面URL
            max_retries: 最大重试次数
            use_cache: 是否使用缓存
            
        Returns:
            HTML内容或None
        """
        if max_retries is None:
            max_retries = AntiBanConfig.MAX_RETRIES
        
        if use_cache:
            cached = page_cache.get_with_meta(url)
            if cached:
                cached_html, meta = cached
            else:
                cached_html, meta = None, {}
        
        # 2. 网络诊断模式 - 仅在debug模式运行
        # if not hasattr(self, '_diagnosed'):
        #     self._diagnosed = True
        #     self._run_network_diagnosis(url)
        
        domain = self._get_domain(url)
        stats = self.domain_stats[domain]
        
        # 3. 使用请求管理器检查是否需要等待
        request_manager.wait_if_needed(domain)
        
        # Cloudflare检测模式
        cloudflare_detected = False
        
        short_content_streak = 0
        force_no_cache = False
        for attempt in range(max_retries):
            try:
                # 设置Cookie
                self._setup_cookies()
                
                # 动态设置请求头
                headers = dict(self.session.headers)
                headers['Referer'] = f"https://{domain}/"
                headers['User-Agent'] = random.choice(self.user_agents)
                
                # 添加更真实的浏览器指纹
                headers['sec-ch-ua'] = '"Chromium";v="128", "Not;A=Brand";v="24", "Google Chrome";v="128"'
                headers['sec-ch-ua-mobile'] = '?0'
                headers['sec-ch-ua-platform'] = '"Windows"'
                if force_no_cache:
                    headers['Cache-Control'] = 'no-cache'
                    headers['Pragma'] = 'no-cache'
                
                # 针对Cloudflare的特殊处理
                if cloudflare_detected:
                    # 遇到Cloudflare时大幅增加等待时间
                    wait_time = request_manager.get_retry_delay(domain, attempt) * 2
                    self.logger.warning(f"Cloudflare检测到，等待{wait_time:.1f}秒...")
                    time.sleep(wait_time)
                elif attempt > 0:
                    # 使用请求管理器的智能重试延迟
                    retry_delay = request_manager.get_retry_delay(domain, attempt)
                    self.logger.info(f"重试 {attempt+1}/{max_retries}，等待 {retry_delay:.1f} 秒")
                    time.sleep(retry_delay)
                
                # 选择代理 - 优先使用直连
                current_proxy = None if attempt == 0 else self.proxies[self.current_proxy_index % len(self.proxies)]
                
                if use_cache and cached_html:
                    if 'etag' in meta:
                        headers['If-None-Match'] = meta['etag']
                    if 'last_modified' in meta:
                        headers['If-Modified-Since'] = meta['last_modified']
                request_manager.enter_request(domain)
                response = self.session.get(
                    url,
                    headers=headers,
                    proxies=current_proxy,
                    timeout=(10, 30),
                    allow_redirects=True,
                    verify=False
                )
                stats['last_request'] = time.time()
                if use_cache and response.status_code == 304 and cached_html:
                    request_manager.record_request(domain, True)
                    if use_cache:
                        page_cache.set(url, cached_html, {
                            'etag': response.headers.get('ETag', meta.get('etag', '')),
                            'last_modified': response.headers.get('Last-Modified', meta.get('last_modified', ''))
                        })
                    self.logger.info(f"✓ 缓存未过期: {url[:50]}...")
                    request_manager.exit_request(domain)
                    return cached_html
                
                # 检测Cloudflare
                is_cloudflare = (
                    response.status_code == 403 or
                    "cloudflare" in response.text.lower() or
                    "just a moment" in response.text.lower() or
                    "ray id" in response.text.lower() or
                    "enable javascript" in response.text.lower() or
                    "checking your browser" in response.text.lower()
                )
                
                # 处理Cloudflare验证
                if is_cloudflare:
                    cloudflare_detected = True
                    self.logger.warning("🛡️  检测到Cloudflare保护")
                    
                    # 如果是首次遇到，给出具体建议
                    if attempt == 0:
                        print("\n" + "="*60)
                        print("🚨 Cloudflare防护检测到")
                        print("💡 解决方案:")
                        print("   1. 使用付费代理服务 (推荐: Bright Data住宅代理)")
                        print("   2. 降低请求频率 (等待30-60秒)")
                        print("   3. 使用真实浏览器环境 (Selenium/Playwright)")
                        print("   4. 考虑使用Cloudflare绕过服务")
                        print("="*60 + "\n")
                    
                    self._adjust_interval(domain, False)
                    self.current_proxy_index += 1
                    request_manager.exit_request(domain)
                    continue
                
                # 处理429状态码
                if response.status_code == 429:
                    retry_after = min(int(response.headers.get('Retry-After', 10)), 30)
                    self.logger.warning(f"⏱️  遇到429限速，等待{retry_after}秒")
                    self._adjust_interval(domain, False)
                    time.sleep(retry_after)
                    request_manager.exit_request(domain)
                    continue
                
                # 处理403状态码（非Cloudflare）
                if response.status_code == 403 and not is_cloudflare:
                    self.logger.warning("🔒 访问被禁止，可能触发反爬机制")
                    self._adjust_interval(domain, False)
                    self.current_proxy_index += 1
                    time.sleep(random.uniform(5, 10))
                    request_manager.exit_request(domain)
                    continue
                
                # 处理500+状态码
                if response.status_code >= 500:
                    self.logger.warning(f"🔥 服务器错误 {response.status_code}，重试中...")
                    self._adjust_interval(domain, False)
                    time.sleep(random.uniform(3, 8))
                    request_manager.exit_request(domain)
                    continue
                
                # 成功响应
                if response.status_code == 200:
                    self._adjust_interval(domain, True)
                    min_len = self.get_min_length_for_domain(domain)
                    html = response.text
                    if self.is_valid_html_for_domain(domain, html):
                        request_manager.record_request(domain, True)
                        if use_cache:
                            page_cache.set(url, html, {
                                'etag': response.headers.get('ETag', ''),
                                'last_modified': response.headers.get('Last-Modified', '')
                            })
                        self.logger.info(f"✓ 成功获取: {url[:50]}...")
                        request_manager.exit_request(domain)
                        return html
                    if len(html) < min_len:
                        short_content_streak += 1
                        snippet = html[:200].replace('\n', ' ')
                        self.logger.warning(f"⚠️  响应内容过短 域名={domain} 尝试={attempt+1}/{max_retries} len={len(html)} 次数={short_content_streak} 片段: {snippet}")
                        if short_content_streak >= 3:
                            request_manager.record_request(domain, False)
                        else:
                            self._adjust_interval(domain, False)
                            force_no_cache = True
                        request_manager.exit_request(domain)
                        continue
                    request_manager.record_request(domain, True)
                    if use_cache:
                        page_cache.set(url, html, {
                            'etag': response.headers.get('ETag', ''),
                            'last_modified': response.headers.get('Last-Modified', '')
                        })
                    self.logger.info(f"✓ 成功获取: {url[:50]}...")
                    request_manager.exit_request(domain)
                    return html
                    
            except requests.exceptions.ProxyError as e:
                self.logger.warning(f"🌐 代理连接失败 (尝试 {attempt+1}/{max_retries}): {str(e)}")
                self._adjust_interval(domain, False)
                request_manager.record_request(domain, False)
                request_manager.exit_request(domain)
                
                # 移除失效代理
                if current_proxy and current_proxy in self.proxies and len(self.proxies) > 1:
                    self.proxies.remove(current_proxy)
                    self.logger.warning(f"🗑️  移除失效代理，剩余 {len(self.proxies)} 个代理")
                    if len(self.proxies) == 1 and self.proxies[0] is None:
                        self.logger.warning("⚠️  所有代理失效，仅使用直连")
                
            except requests.exceptions.ConnectionError as e:
                error_msg = str(e)
                if "ConnectionResetError" in str(type(e).__name__) or "10054" in error_msg:
                    self.logger.warning(f"🔌 连接被重置 (尝试 {attempt+1}/{max_retries})")
                    
                    # 区分不同类型的连接重置
                    if "10054" in error_msg:
                        print("\n" + "="*60)
                        print("🔌 连接被远程主机强制关闭 (错误10054)")
                        print("💡 可能原因:")
                        print("   • 目标网站主动拒绝连接")
                        print("   • 网络防火墙拦截")
                        print("   • ISP限制访问")
                        print("   • 代理服务器问题")
                        print("="*60 + "\n")
                    
                else:
                    self.logger.warning(f"🔗 连接错误: {error_msg}")
                
                self._adjust_interval(domain, False)
                request_manager.record_request(domain, False)
                request_manager.exit_request(domain)
                
            except requests.exceptions.Timeout as e:
                self.logger.warning(f"⏰ 请求超时: {str(e)}")
                self._adjust_interval(domain, False)
                request_manager.record_request(domain, False)
                request_manager.exit_request(domain)
                
            except Exception as e:
                self.logger.error(f"❗ 未知错误: {type(e).__name__}: {str(e)}")
                self._adjust_interval(domain, False)
                request_manager.record_request(domain, False)
                request_manager.exit_request(domain)
        
        self.logger.error(f"🚫 达到最大重试次数，无法获取页面内容")
        print("\n" + "="*60)
        print("🚫 所有重试失败")
        print("💡 最终建议:")
        print("   1. 使用付费代理服务 (住宅代理 > 数据中心代理)")
        print("   2. 切换到真实浏览器自动化 (Selenium/Playwright)")
        print("   3. 降低请求频率到每请求间隔60秒以上")
        print("   4. 考虑使用Cloudflare绕过API服务")
        print("="*60 + "\n")
        return None

    def parse_video_info(self, html: str, base_url: str) -> List[Dict]:
        try:
            self.logger.info("开始解析视频信息")
            soup = BeautifulSoup(html, 'lxml')
            videos = []
            
            # 查找所有视频容器 - 使用多种通用选择器
            video_containers = []
            
            # 优先选择器列表 - 基于实际页面结构
            selectors = [
                '.col-xs-6.col-md-3',  # hsex.men主选择器
                '.thumbnail',          # hsex.men内部容器
                '.video-item',
                '.item',
                '.card',
                '.video-card',
                '.content-item',
                'div[class*="video"]',
                'div[class*="item"]',
                '.gallery-item',
                '.thumb-item'
            ]
            
            # 尝试每个选择器
            for selector in selectors:
                containers = soup.select(selector)
                if containers:
                    video_containers = containers
                    self.logger.debug(f"使用选择器 '{selector}' 找到 {len(containers)} 个视频容器")
                    break
            
            # 如果没有找到，尝试通过视频链接查找容器
            if not video_containers:
                all_links = soup.select('a[href*="video"], a[href*="watch"], a[href*="play"], a[href*="view"]')
                containers = []
                for link in all_links:
                    parent = link.find_parent(['div', 'article', 'section', 'li'])
                    if parent and parent not in containers:
                        containers.append(parent)
                video_containers = containers
                self.logger.debug(f"通过链接找到 {len(video_containers)} 个视频容器")
            
            self.logger.debug(f"总共找到 {len(video_containers)} 个视频容器")
            
            for container in video_containers:
                try:
                    # 使用通用方法提取信息
                    video_id = self._extract_video_id(container)
                    title = self._extract_title(container)
                    thumbnail_url = self._extract_thumbnail(container, base_url)
                    time_text = self._extract_time(container)
                    
                    # 清理时间文本，移除观看次数等信息
                    if time_text:
                        time_text = re.sub(r'\d+.*?(次观看|views|播放|view|Views|次播放)', '', time_text, flags=re.IGNORECASE).strip()
                        if not time_text:
                            time_text = '最近更新'
                    else:
                        time_text = '最近更新'
                    
                    video_info = {
                        'video_id': video_id,
                        'title': title,
                        'thumbnail_url': thumbnail_url,
                        'relative_time': time_text,
                        'upload_time': self._parse_relative_time(time_text)
                    }
                    
                    self.logger.debug(f"解析到视频信息: {video_info}")
                    
                    # 只要有标题就认为是有效的（适配hsex.men可能不需要video_id）
                    if title:
                        videos.append(video_info)
                        
                except Exception as e:
                    self.logger.error(f"解析单个视频项时出错: {str(e)}")
                    continue
            
            self.logger.info(f"成功解析 {len(videos)} 个视频信息")
            return videos
            
        except Exception as e:
            self.logger.error(f"解析视频信息失败: {str(e)}", exc_info=True)
            return []

    def _extract_video_id(self, item) -> str:
        try:
            # 从视频链接中提取ID
            video_link = None
            # 尝试多种可能的链接选择器
            for selector in ['a[href*="video"]', 'a[href*="watch"]', 'a[href*="play"]', 'a[href*="view"]', 'a[href*="movie"]']:
                video_link = item.select_one(selector)
                if video_link:
                    break
            
            if video_link and 'href' in video_link.attrs:
                href = video_link['href']
                self.logger.debug(f"找到视频链接: {href}")
                
                # 尝试多种ID提取模式，适配hsex.men和通用格式
                patterns = [
                    r'video-(\d+)\.htm',           # hsex.men格式: video-12345.htm
                    r'video/(\d+)',                # /video/12345
                    r'watch\?(?:.*&)?v=(\w+)',     # watch?v=abc123
                    r'play/(\d+)',                  # /play/12345
                    r'movie/(\d+)',                 # /movie/12345
                    r'id=(\d+)',                    # ?id=12345
                    r'/(\d+)(?:/|$)',               # 纯数字ID
                    r'[?&]v=([^&]+)',                # URL参数中的v值
                    r'embed/(\w+)',                  # embed/abc123
                    r'v/(\w+)',                      # /v/abc123
                    r'view/(\d+)'                    # /view/12345
                ]
                
                for pattern in patterns:
                    match = re.search(pattern, href)
                    if match:
                        video_id = match.group(1)
                        self.logger.debug(f"提取到视频ID: {video_id}")
                        return video_id
                        
                # 如果URL是数字结尾，尝试提取
                numeric_match = re.search(r'(\d+)(?:\.\w+)?$', href)
                if numeric_match:
                    video_id = numeric_match.group(1)
                    self.logger.debug(f"提取到数字ID: {video_id}")
                    return video_id
                    
            return ''
        except Exception as e:
            self.logger.error(f"提取视频ID失败: {str(e)}")
            return ''

    def _extract_title(self, item) -> str:
        try:
            # 基于hsex.men网站结构的标题选择器
            selectors = [
                '.title h5 a',           # hsex.men主标题选择器
                '.title a',              # hsex.men备用标题选择器
                '.video-title',
                '.title',
                'h3',
                'a[title]',
                '.item-title',
                '.video-name',
                '.name',
                '.description',
                'p',
                'a'
            ]
            
            for selector in selectors:
                title_elem = item.select_one(selector)
                if title_elem:
                    # 尝试不同的属性获取标题
                    for attr in ['title', 'alt', 'data-title']:
                        if attr in title_elem.attrs:
                            title = title_elem[attr].strip()
                            if title:
                                self.logger.debug(f"从属性 {attr} 找到标题: {title}")
                                return title
                    
                    # 获取文本内容
                    title = title_elem.text.strip()
                    if title:
                        self.logger.debug(f"从文本找到标题: {title}")
                        return title
            
            return ''
        except Exception as e:
            self.logger.error(f"提取标题失败: {str(e)}")
            return ''

    def _extract_thumbnail(self, item, base_url: str) -> str:
        try:
            # 尝试从img标签提取
            img = item.select_one('img[src]')
            if img and 'src' in img.attrs:
                src = img['src']
                if src.startswith('//'):
                    return f'https:{src}'
                elif src.startswith('/'):
                    return urljoin(base_url, src)
                return src
            
            # 尝试从background-image样式提取
            image_div = item.select_one('.image')
            if image_div:
                style = image_div.get('style', '')
                match = re.search(r'background-image:\s*url\(["\']?([^"\']+)["\']?\)', style)
                if match:
                    url = match.group(1)
                    if url.startswith('//'):
                        return f'https:{url}'
                    elif url.startswith('/'):
                        return urljoin(base_url, url)
                    return url
            
            return ''
        except Exception as e:
            self.logger.error(f"Error extracting thumbnail: {str(e)}")
            return ''

    def _extract_time(self, item) -> str:
        try:
            # 基于hsex.men网站结构的时间选择器
            time_elem = (
                item.select_one('.info p') or            # hsex.men上传时间选择器
                item.select_one('.upload-time') or
                item.select_one('.time') or
                item.select_one('time') or
                item.select_one('.date')
            )
            
            if time_elem:
                text = time_elem.text.strip()
                # 提取时间信息（如"1月前"、"2月前"）
                import re
                time_match = re.search(r'(\d+(?:\.\d+)?[kK]?次观看\s+)(.+)', text)
                if time_match:
                    return time_match.group(2).strip()
                return text
            return ''
        except Exception as e:
            self.logger.error(f"Error extracting time: {str(e)}")
            return ''

    def _parse_relative_time(self, time_str: str) -> datetime:
        """将时间字符串转换为datetime对象"""
        try:
            if not time_str or time_str == '最近更新':
                return datetime.now()

            self.logger.debug(f"解析时间字符串: {time_str}")
            
            # 清理字符串，移除多余的空白字符和特殊字符
            time_str = ' '.join(time_str.split())
            time_str = re.sub(r'[^\w\s\-:]+', '', time_str).strip()
            
            # 首先尝试解析完整日期格式
            date_patterns = [
                r'(\d{4})-(\d{1,2})-(\d{1,2})',  # YYYY-MM-DD
                r'(\d{1,2})-(\d{1,2})-(\d{4})',  # DD-MM-YYYY
                r'(\d{1,2})/(\d{1,2})/(\d{4})',   # MM/DD/YYYY
                r'(\d{4})/(\d{1,2})/(\d{1,2})'    # YYYY/MM/DD
            ]
            
            for pattern in date_patterns:
                match = re.search(pattern, time_str)
                if match:
                    groups = match.groups()
                    if len(groups) == 3:
                        # 根据格式确定年月日
                        if pattern.startswith(r'(\d{4})'):
                            year, month, day = int(groups[0]), int(groups[1]), int(groups[2])
                        elif pattern.startswith(r'(\d{1,2})-(\d{1,2})-(\d{4})'):
                            day, month, year = int(groups[0]), int(groups[1]), int(groups[2])
                        else:
                            month, day, year = int(groups[0]), int(groups[1]), int(groups[2])
                        
                        try:
                            return datetime(year, month, day)
                        except ValueError:
                            continue

            # 解析相对时间 - 英文格式
            now = datetime.now()
            
            # 英文时间格式
            patterns = [
                (r'(\d+)\s*day[s]?\s*ago', 'days'),
                (r'(\d+)\s*hour[s]?\s*ago', 'hours'),
                (r'(\d+)\s*minute[s]?\s*ago', 'minutes'),
                (r'(\d+)\s*week[s]?\s*ago', 'weeks'),
                (r'(\d+)\s*month[s]?\s*ago', 'months'),
                (r'(\d+)\s*year[s]?\s*ago', 'years'),
                # 中文格式
                (r'(\d+)\s*天前', 'days'),
                (r'(\d+)\s*小时前', 'hours'),
                (r'(\d+)\s*分钟前', 'minutes'),
                (r'(\d+)\s*周前', 'weeks'),
                (r'(\d+)\s*月前', 'months'),
                (r'(\d+)\s*年前', 'years')
            ]
            
            for pattern, unit in patterns:
                match = re.search(pattern, time_str, re.IGNORECASE)
                if match:
                    value = int(match.group(1))
                    if unit == 'days':
                        return now - timedelta(days=value)
                    elif unit == 'hours':
                        return now - timedelta(hours=value)
                    elif unit == 'minutes':
                        return now - timedelta(minutes=value)
                    elif unit == 'weeks':
                        return now - timedelta(weeks=value)
                    elif unit == 'months':
                        return now - timedelta(days=30*value)
                    elif unit == 'years':
                        return now - timedelta(days=365*value)
            
            # 尝试解析英文月份格式
            month_patterns = [
                r'(\w+)\s+(\d{1,2}),?\s+(\d{4})',  # Month DD, YYYY
                r'(\d{1,2})\s+(\w+)\s+(\d{4})',  # DD Month YYYY
            ]
            
            month_map = {
                'jan': 1, 'january': 1, 'feb': 2, 'february': 2, 'mar': 3, 'march': 3,
                'apr': 4, 'april': 4, 'may': 5, 'jun': 6, 'june': 6,
                'jul': 7, 'july': 7, 'aug': 8, 'august': 8,
                'sep': 9, 'september': 9, 'oct': 10, 'october': 10,
                'nov': 11, 'november': 11, 'dec': 12, 'december': 12
            }
            
            for pattern in month_patterns:
                match = re.search(pattern, time_str, re.IGNORECASE)
                if match:
                    groups = match.groups()
                    if len(groups) == 3:
                        # 解析月份
                        month_str = groups[0].lower() if groups[0].isalpha() else groups[1].lower()
                        month = month_map.get(month_str, 1)
                        
                        # 解析日和年
                        if groups[0].isdigit():
                            day = int(groups[0])
                            year = int(groups[2])
                        else:
                            day = int(groups[1])
                            year = int(groups[2])
                        
                        try:
                            return datetime(year, month, day)
                        except ValueError:
                            continue
            
            self.logger.warning(f"无法解析的时间格式: {time_str}")
            return datetime.now()
            
        except Exception as e:
            self.logger.error(f"解析时间失败: {str(e)}")
            return datetime.now()
