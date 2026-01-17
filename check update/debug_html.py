#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HTML内容调试脚本 - 增强版
用于分析实际获取的页面内容，包括响应头信息
"""

import requests
from bs4 import BeautifulSoup
import os
import json
import gzip
import io
import re

def debug_response_details():
    """调试响应详细信息"""
    print("🔍 开始调试响应详细信息...")
    
    # 测试URL
    test_url = "https://hsex.men/user.htm?author=345061255"
    
    # 设置请求头
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Cache-Control': 'max-age=0'
    }
    
    try:
        print(f"📡 获取页面: {test_url}")
        
        # 获取响应
        response = requests.get(test_url, headers=headers, timeout=10)
        
        print(f"📊 响应状态: {response.status_code}")
        print(f"📊 响应头: {dict(response.headers)}")
        print(f"📊 编码: {response.encoding}")
        print(f"📊 内容长度: {len(response.content)} 字节")
        
        # 检查内容类型
        content_type = response.headers.get('content-type', 'unknown')
        print(f"📊 内容类型: {content_type}")
        
        # 检查是否是压缩内容
        if 'gzip' in response.headers.get('content-encoding', ''):
            print("📊 检测到gzip压缩")
            # 尝试解压
            try:
                decompressed = gzip.decompress(response.content)
                print(f"📊 解压后长度: {len(decompressed)} 字节")
                content = decompressed.decode('utf-8', errors='ignore')
            except:
                content = response.text
        else:
            content = response.text
        
        # 保存原始内容
        with open('debug_response.txt', 'w', encoding='utf-8') as f:
            f.write(f"Status: {response.status_code}\n")
            f.write(f"Headers: {dict(response.headers)}\n")
            f.write(f"Content-Type: {content_type}\n")
            f.write("-" * 50 + "\n")
            f.write(content)
        
        # 保存二进制内容用于分析
        with open('debug_response.bin', 'wb') as f:
            f.write(response.content)
        
        print(f"📄 响应已保存到 debug_response.txt 和 debug_response.bin")
        
        # 尝试解析内容
        if 'text/html' in content_type:
            soup = BeautifulSoup(content, 'lxml')
            
            print(f"📊 页面基本信息:")
            print(f"   标题: {soup.title.string if soup.title else '无标题'}")
            print(f"   body标签: {'存在' if soup.body else '不存在'}")
            
            # 检查是否是Cloudflare页面
            if 'cloudflare' in content.lower() or 'ray id' in content.lower():
                print("⚠️  检测到Cloudflare防护页面")
                
                # 查找Ray ID
                ray_match = re.search(r'Ray ID: ([a-f0-9]+)', content)
                if ray_match:
                    print(f"   Ray ID: {ray_match.group(1)}")
            
            # 检查是否是登录页面
            if 'login' in content.lower() or 'sign in' in content.lower():
                print("⚠️  检测到登录页面")
            
            # 打印前500字符的内容预览
            preview = content[:500]
            print(f"📄 内容预览: {preview}")
            
            # 分析页面结构
            if soup.body:
                print(f"📊 页面结构:")
                print(f"   所有标签: {len(soup.find_all())}")
                print(f"   div标签: {len(soup.find_all('div'))}")
                print(f"   a标签: {len(soup.find_all('a'))}")
                print(f"   img标签: {len(soup.find_all('img'))}")
                
                # 查找可能的视频容器
                video_selectors = [
                    'div[class*="video"]',
                    'div[class*="item"]',
                    'a[href*="video"]',
                    'a[href*="watch"]',
                    'img[src*="jpg"]',
                    'img[src*="png"]'
                ]
                
                for selector in video_selectors:
                    elements = soup.select(selector)
                    if elements:
                        print(f"   ✅ {selector}: {len(elements)} 个")
        else:
            print("❌ 返回内容不是HTML")
            
    except Exception as e:
        print(f"❌ 请求出错: {e}")
        import traceback
        traceback.print_exc()

def test_different_urls():
    """测试不同的URL格式"""
    print("\n" + "="*60)
    print("🔗 测试不同URL格式...")
    
    urls = [
        "https://hsex.men",
        "https://hsex.men/",
        "https://hsex.men/user.htm?author=345061255",
        "https://hsex.men/user/345061255",
        "https://hsex.men/profile/345061255"
    ]
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    for url in urls:
        try:
            print(f"\n📡 测试: {url}")
            response = requests.get(url, headers=headers, timeout=5)
            print(f"   状态码: {response.status_code}")
            print(f"   内容长度: {len(response.content)} 字节")
            
            # 检查是否是HTML
            if 'text/html' in response.headers.get('content-type', ''):
                soup = BeautifulSoup(response.text, 'lxml')
                print(f"   标题: {soup.title.string if soup.title else '无标题'}")
                print(f"   div数量: {len(soup.find_all('div'))}")
            else:
                print(f"   内容类型: {response.headers.get('content-type')}")
                
        except Exception as e:
            print(f"   ❌ 错误: {e}")

if __name__ == "__main__":
    debug_response_details()
    test_different_urls()
    
    print("\n" + "="*60)
    print("💡 调试完成！")
    print("📁 查看生成的 debug_response.txt 和 debug_response.bin")
    print("🔍 分析响应内容类型和结构")
    print("="*60)