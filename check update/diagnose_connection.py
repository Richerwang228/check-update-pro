#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
网络连接诊断脚本
用于分析hsex.men网站的访问问题并提供解决方案
"""

import requests
import socket
import time
import random
from urllib.parse import urlparse
import ssl
import warnings
warnings.filterwarnings('ignore')

class ConnectionDiagnoser:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0'
        })

    def test_dns_resolution(self, hostname):
        """测试DNS解析"""
        print(f"🔍 测试DNS解析: {hostname}")
        try:
            ip = socket.gethostbyname(hostname)
            print(f"✅ DNS解析成功: {hostname} -> {ip}")
            return True, ip
        except socket.gaierror as e:
            print(f"❌ DNS解析失败: {e}")
            return False, None

    def test_port_connectivity(self, hostname, port=443):
        """测试端口连接"""
        print(f"🔌 测试端口连接: {hostname}:{port}")
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex((hostname, port))
            sock.close()
            
            if result == 0:
                print(f"✅ 端口连接成功")
                return True
            else:
                print(f"❌ 端口连接失败 (错误码: {result})")
                return False
        except Exception as e:
            print(f"❌ 端口测试异常: {e}")
            return False

    def test_ssl_handshake(self, hostname):
        """测试SSL握手"""
        print(f"🔒 测试SSL握手: {hostname}")
        try:
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10)
            sock.connect((hostname, 443))
            
            ssl_sock = context.wrap_socket(sock, server_hostname=hostname)
            ssl_sock.close()
            
            print(f"✅ SSL握手成功")
            return True
        except Exception as e:
            print(f"❌ SSL握手失败: {e}")
            return False

    def test_http_request(self, url, use_proxy=False, proxy=None):
        """测试HTTP请求"""
        print(f"🌐 测试HTTP请求: {url}")
        if use_proxy and proxy:
            print(f"   使用代理: {proxy}")
        
        proxies = {'http': proxy, 'https': proxy} if use_proxy and proxy else None
        
        try:
            start_time = time.time()
            response = self.session.get(
                url,
                proxies=proxies,
                timeout=15,
                allow_redirects=True,
                verify=False
            )
            end_time = time.time()
            
            response_time = end_time - start_time
            print(f"✅ HTTP请求成功")
            print(f"   状态码: {response.status_code}")
            print(f"   响应时间: {response_time:.2f}s")
            print(f"   内容长度: {len(response.text)}字符")
            
            # 检测Cloudflare
            if self.detect_cloudflare(response):
                print("🛡️  检测到Cloudflare防护")
                return False, response
            
            return True, response
            
        except requests.exceptions.ConnectionError as e:
            print(f"❌ 连接错误: {e}")
            return False, None
        except requests.exceptions.Timeout as e:
            print(f"⏰ 请求超时: {e}")
            return False, None
        except requests.exceptions.ProxyError as e:
            print(f"🌐 代理错误: {e}")
            return False, None
        except Exception as e:
            print(f"❗ 未知错误: {e}")
            return False, None

    def detect_cloudflare(self, response):
        """检测Cloudflare防护"""
        cloudflare_indicators = [
            'cloudflare',
            'ray id',
            'just a moment',
            'checking your browser',
            'enable javascript',
            'cf-ray',
            '__cfduid'
        ]
        
        text_lower = response.text.lower()
        headers_lower = {k.lower(): v.lower() for k, v in response.headers.items()}
        
        # 检查响应内容
        for indicator in cloudflare_indicators:
            if indicator in text_lower:
                return True
        
        # 检查响应头
        if 'server' in headers_lower and 'cloudflare' in headers_lower['server']:
            return True
        if 'cf-ray' in headers_lower:
            return True
            
        return False

    def test_proxy_list(self, proxies):
        """测试代理列表"""
        print("\n🌐 测试代理列表...")
        working_proxies = []
        
        test_url = "https://httpbin.org/ip"
        
        for i, proxy in enumerate(proxies):
            if proxy is None:
                print(f"📡 测试直连...")
                success, response = self.test_http_request(test_url)
                if success:
                    working_proxies.append(None)
                    print(f"✅ 直连可用")
                continue
                
            print(f"🌐 测试代理 {i+1}: {proxy}")
            success, response = self.test_http_request(test_url, use_proxy=True, proxy=proxy)
            if success:
                working_proxies.append(proxy)
                print(f"✅ 代理 {i+1} 可用")
            else:
                print(f"❌ 代理 {i+1} 不可用")
                
        return working_proxies

    def run_full_diagnosis(self, target_url):
        """运行完整诊断"""
        print("🔍 开始网络连接诊断")
        print("=" * 60)
        
        parsed_url = urlparse(target_url)
        hostname = parsed_url.hostname
        
        # 1. DNS解析测试
        dns_success, ip = self.test_dns_resolution(hostname)
        if not dns_success:
            return self.generate_recommendations("dns_failure")
        
        # 2. 端口连接测试
        port_success = self.test_port_connectivity(hostname)
        if not port_success:
            return self.generate_recommendations("port_failure")
        
        # 3. SSL握手测试
        ssl_success = self.test_ssl_handshake(hostname)
        if not ssl_success:
            return self.generate_recommendations("ssl_failure")
        
        # 4. HTTP请求测试
        http_success, response = self.test_http_request(target_url)
        
        if http_success:
            print("\n🎉 所有测试通过！")
            return True
        else:
            if response and self.detect_cloudflare(response):
                return self.generate_recommendations("cloudflare_block")
            else:
                return self.generate_recommendations("http_failure")

    def generate_recommendations(self, issue_type):
        """生成故障排除建议"""
        recommendations = {
            "dns_failure": [
                "检查网络连接",
                "更换DNS服务器 (8.8.8.8, 1.1.1.1)",
                "检查hosts文件",
                "联系网络服务提供商"
            ],
            "port_failure": [
                "检查防火墙设置",
                "确认443端口未被封锁",
                "尝试使用VPN",
                "联系网络管理员"
            ],
            "ssl_failure": [
                "更新SSL证书库",
                "检查系统时间",
                "尝试使用HTTP而非HTTPS",
                "禁用SSL验证 (不推荐)"
            ],
            "cloudflare_block": [
                "使用付费代理服务 (Bright Data, Oxylabs)",
                "降低请求频率到60秒以上",
                "使用真实浏览器自动化 (Selenium)",
                "考虑使用Cloudflare绕过API"
            ],
            "http_failure": [
                "检查网络连接",
                "尝试使用代理",
                "清除浏览器缓存",
                "等待一段时间后重试"
            ]
        }
        
        print(f"\n🚨 检测到问题类型: {issue_type}")
        print("💡 解决方案:")
        for i, rec in enumerate(recommendations.get(issue_type, []), 1):
            print(f"   {i}. {rec}")
        
        return False

def main():
    """主函数"""
    print("🔍 hsex.men 网络连接诊断工具")
    print("=" * 60)
    
    target_url = "https://hsex.men/user.htm?author=345061255"
    
    diagnoser = ConnectionDiagnoser()
    success = diagnoser.run_full_diagnosis(target_url)
    
    if success:
        print("\n✅ 网络连接正常，可以开始爬取")
    else:
        print("\n❌ 检测到网络问题，请根据建议解决")
    
    print("\n" + "=" * 60)
    print("📞 如需进一步帮助:")
    print("   • 运行: python diagnose_connection.py")
    print("   • 检查日志文件获取详细信息")
    print("   • 考虑使用付费代理服务")

if __name__ == "__main__":
    main()