#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试更新后的解析器
验证是否可以正确解析hsex.men网站的视频信息
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.web_scraper import WebScraper
from bs4 import BeautifulSoup

def test_parser():
    """测试解析器"""
    print("🧪 测试更新后的解析器...")
    
    # 读取之前保存的HTML文件
    try:
        with open('user_page.html', 'r', encoding='utf-8') as f:
            html = f.read()
        print("📄 使用已保存的HTML文件进行测试")
    except FileNotFoundError:
        print("❌ 未找到user_page.html，请先运行analyze_user_page.py")
        return
    
    # 创建解析器实例
    scraper = WebScraper()
    
    # 测试解析
    videos = scraper.parse_video_info(html, "https://hsex.men")
    
    print(f"\n✅ 解析完成！找到 {len(videos)} 个视频")
    
    if videos:
        print("\n📋 解析结果:")
        for i, video in enumerate(videos[:5]):
            print(f"\n{i+1}. 视频信息:")
            print(f"   📹 ID: {video.get('video_id', '无')}")
            print(f"   📝 标题: {video.get('title', '无')}")
            print(f"   🖼️ 缩略图: {video.get('thumbnail_url', '无')}")
            print(f"   ⏱️ 时长: {video.get('relative_time', '无')}")
    else:
        print("❌ 未解析到任何视频")
        
        # 调试信息
        soup = BeautifulSoup(html, 'lxml')
        containers = soup.select('.col-xs-6.col-md-3')
        print(f"\n🔍 调试信息:")
        print(f"   找到 {len(containers)} 个.col-xs-6.col-md-3容器")
        
        if containers:
            container = containers[0]
            print(f"   容器HTML示例:")
            print(f"   {container.prettify()[:300]}...")

if __name__ == "__main__":
    test_parser()