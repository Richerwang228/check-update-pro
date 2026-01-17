#!/usr/bin/env python3
"""
连接测试脚本
用于验证反爬策略和网络连接是否正常
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'services'))
sys.path.append(os.path.join(os.path.dirname(__file__), 'config'))

from web_scraper import WebScraper
import logging
import time

def setup_logging():
    """设置日志"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('test_connection.log', encoding='utf-8')
        ]
    )

def test_basic_connection():
    """测试基本连接"""
    print("=== 测试基本连接 ===")
    
    scraper = WebScraper()
    test_urls = [
        'https://hsex.men/',
        'https://hsex.men/video',
        'https://hsex.men/page/2'
    ]
    
    for url in test_urls:
        print(f"\n测试URL: {url}")
        try:
            content = scraper.get_page_content(url, max_retries=3)
            if content:
                print(f"✅ 成功获取内容，长度: {len(content)} 字符")
                
                # 检查是否被重定向到验证页面
                if 'cloudflare' in content.lower() or '验证' in content.lower():
                    print("⚠️  检测到验证页面")
                elif 'hsex' in content.lower():
                    print("✅ 成功访问目标页面")
                else:
                    print("⚠️  可能访问了错误页面")
                    
            else:
                print("❌ 获取内容失败")
                
        except Exception as e:
            print(f"❌ 异常: {str(e)}")
        
        time.sleep(2)  # 测试间隔

def test_proxy_rotation():
    """测试代理轮换"""
    print("\n=== 测试代理轮换 ===")
    
    scraper = WebScraper()
    
    # 强制使用不同的代理
    for i, proxy in enumerate(scraper.proxies):
        print(f"\n测试代理 {i}: {proxy}")
        scraper.current_proxy_index = i
        
        try:
            content = scraper.get_page_content('https://hsex.men/', max_retries=2)
            if content:
                print(f"✅ 代理 {i} 工作正常")
            else:
                print(f"❌ 代理 {i} 失败")
        except Exception as e:
            print(f"❌ 代理 {i} 异常: {str(e)}")

def test_rate_limiting():
    """测试速率限制"""
    print("\n=== 测试速率限制 ===")
    
    scraper = WebScraper()
    
    # 快速连续请求测试
    for i in range(5):
        print(f"\n快速请求 {i+1}/5")
        start_time = time.time()
        
        try:
            content = scraper.get_page_content('https://hsex.men/', max_retries=1)
            elapsed = time.time() - start_time
            
            if content:
                print(f"✅ 成功，耗时: {elapsed:.2f}秒")
            else:
                print(f"❌ 失败，耗时: {elapsed:.2f}秒")
                
        except Exception as e:
            elapsed = time.time() - start_time
            print(f"❌ 异常，耗时: {elapsed:.2f}秒，错误: {str(e)}")

def test_user_agents():
    """测试不同的User-Agent"""
    print("\n=== 测试User-Agent轮换 ===")
    
    scraper = WebScraper()
    
    for i, ua in enumerate(scraper.user_agents[:3]):  # 测试前3个
        print(f"\n测试UA {i+1}: {ua[:50]}...")
        
        # 强制使用特定UA
        scraper.session.headers['User-Agent'] = ua
        
        try:
            content = scraper.get_page_content('https://hsex.men/', max_retries=2)
            if content:
                print(f"✅ UA {i+1} 工作正常")
            else:
                print(f"❌ UA {i+1} 失败")
        except Exception as e:
            print(f"❌ UA {i+1} 异常: {str(e)}")

def main():
    """主测试函数"""
    setup_logging()
    
    print("🚀 开始连接测试...")
    print("=" * 50)
    
    try:
        test_basic_connection()
        test_proxy_rotation()
        test_rate_limiting()
        test_user_agents()
        
        print("\n" + "=" * 50)
        print("✅ 测试完成！")
        print("查看 test_connection.log 获取详细日志")
        
    except KeyboardInterrupt:
        print("\n❌ 测试被中断")
    except Exception as e:
        print(f"\n❌ 测试异常: {str(e)}")

if __name__ == "__main__":
    main()