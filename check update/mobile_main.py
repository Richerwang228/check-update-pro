#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pydroid 3专用简化版主程序
去掉了Qt界面，用命令行操作
"""

import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.web_scraper import WebScraper
import logging

# 配置日志为简单格式
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'
)

def mobile_menu():
    """移动端菜单"""
    print("\n📱 hsex.men 视频爬虫")
    print("=" * 30)
    print("1. 爬取用户视频")
    print("2. 测试网络连接")
    print("3. 退出")
    print("=" * 30)

def scrape_user_videos():
    """爬取用户视频"""
    scraper = WebScraper()
    
    # 默认用户ID
    user_id = "345061255"
    print(f"\n🔄 正在爬取用户 {user_id} 的视频...")
    
    try:
        url = f"https://hsex.men/user.htm?author={user_id}"
        videos = scraper.scrape_videos(url)
        
        if videos:
            print(f"\n✅ 找到 {len(videos)} 个视频：\n")
            for i, video in enumerate(videos, 1):
                print(f"{i}. 📹 {video.get('title', '无标题')}")
                print(f"   ⏱️ {video.get('relative_time', '未知时间')}")
                print(f"   👁️ {video.get('views', '未知观看')}")
                print()
        else:
            print("❌ 未找到视频或网络错误")
            
    except Exception as e:
        print(f"❌ 错误: {str(e)}")

def test_connection():
    """测试网络"""
    import requests
    try:
        response = requests.get("https://hsex.men", timeout=10)
        print(f"✅ 网络连接正常 (状态码: {response.status_code})")
    except Exception as e:
        print(f"❌ 网络连接失败: {str(e)}")

if __name__ == "__main__":
    while True:
        mobile_menu()
        choice = input("\n请选择 (1-3): ").strip()
        
        if choice == "1":
            scrape_user_videos()
        elif choice == "2":
            test_connection()
        elif choice == "3":
            print("👋 再见！")
            break
        else:
            print("❌ 无效选择")