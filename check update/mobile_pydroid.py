#!/usr/bin/env python3
"""
Pydroid 3 专用版本 - 使用PySide6
支持hsex.men视频爬虫
"""

import sys
import os
import logging
from datetime import datetime
import requests
from bs4 import BeautifulSoup
import re
import time

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class HsexVideoScraper:
    """hsex.men视频爬虫类"""
    
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Connection': 'keep-alive',
        }
    
    def get_user_videos(self, username, max_pages=3):
        """获取用户所有视频"""
        videos = []
        base_url = f"https://hsex.men/author/{username}"
        
        for page in range(1, max_pages + 1):
            url = f"{base_url}/{page}"
            logger.info(f"正在爬取第{page}页: {url}")
            
            try:
                response = requests.get(url, headers=self.headers, timeout=10)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.text, 'lxml')
                
                # 查找视频容器
                video_containers = soup.select('.col-xs-6.col-md-3')
                logger.info(f"第{page}页找到 {len(video_containers)} 个视频")
                
                if not video_containers:
                    logger.warning(f"第{page}页没有找到视频，可能已到达最后一页")
                    break
                
                for container in video_containers:
                    video = self._extract_video_info(container)
                    if video:
                        videos.append(video)
                
                # 添加延迟避免被封
                time.sleep(1)
                
            except requests.exceptions.RequestException as e:
                logger.error(f"请求失败: {str(e)}")
                break
            except Exception as e:
                logger.error(f"解析页面出错: {str(e)}")
                continue
        
        return videos
    
    def _extract_video_info(self, container):
        """从容器提取视频信息"""
        try:
            video = {}
            
            # 提取视频链接和ID
            link_elem = container.find('a')
            if link_elem and link_elem.get('href'):
                href = link_elem['href']
                video['url'] = f"https://hsex.men{href}" if href.startswith('/') else href
                # 从URL提取视频ID
                match = re.search(r'video-(\d+)\.htm', href)
                if match:
                    video['id'] = match.group(1)
                else:
                    video['id'] = href.split('/')[-1].replace('.htm', '')
            
            # 提取缩略图
            img_container = container.find('div', class_='thumb')
            if img_container:
                style = img_container.get('style', '')
                bg_match = re.search(r'background-image:\s*url\(["\']?([^"\']+)["\']?\)', style)
                if bg_match:
                    video['thumbnail'] = bg_match.group(1)
                    if video['thumbnail'].startswith('//'):
                        video['thumbnail'] = 'https:' + video['thumbnail']
                    elif video['thumbnail'].startswith('/'):
                        video['thumbnail'] = 'https://hsex.men' + video['thumbnail']
            
            # 提取标题
            title_elem = container.select_one('.title h5 a') or container.select_one('.title a')
            if title_elem:
                video['title'] = title_elem.get_text(strip=True)
            
            # 提取时长/更新时间
            info_elem = container.find('p')
            if info_elem:
                info_text = info_elem.get_text(strip=True)
                # 查找"X月前"格式的时间
                time_match = re.search(r'(\d+月前|\d+天前|\d+年前)', info_text)
                if time_match:
                    video['upload_time'] = time_match.group(1)
                else:
                    video['upload_time'] = "未知"
            
            # 提取时长（如果有duration类）
            duration_elem = container.find('span', class_='duration')
            if duration_elem:
                video['duration'] = duration_elem.get_text(strip=True)
            
            return video if video.get('title') and video.get('url') else None
            
        except Exception as e:
            logger.error(f"提取视频信息失败: {str(e)}")
            return None
    
    def test_connection(self):
        """测试网络连接"""
        try:
            response = requests.get("https://hsex.men", headers=self.headers, timeout=5)
            if response.status_code == 200:
                logger.info("✅ 网络连接正常")
                return True
            else:
                logger.warning(f"⚠️ 网站返回状态码: {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"❌ 网络连接失败: {str(e)}")
            return False

class MobileApp:
    """移动端应用类"""
    
    def __init__(self):
        self.scraper = HsexVideoScraper()
    
    def display_menu(self):
        """显示菜单"""
        print("\n" + "="*50)
        print("📱 hsex.men 视频爬虫 (Pydroid 3版)")
        print("="*50)
        print("1. 爬取用户视频")
        print("2. 测试网络连接")
        print("3. 查看使用说明")
        print("4. 退出")
        print("="*50)
    
    def run(self):
        """运行应用"""
        print("🚀 启动hsex.men视频爬虫...")
        
        while True:
            self.display_menu()
            choice = input("\n请选择操作 (1-4): ").strip()
            
            if choice == '1':
                self.scrape_user_videos()
            elif choice == '2':
                self.test_connection()
            elif choice == '3':
                self.show_instructions()
            elif choice == '4':
                print("👋 感谢使用，再见！")
                break
            else:
                print("❌ 无效选择，请输入1-4")
    
    def scrape_user_videos(self):
        """爬取用户视频"""
        username = input("请输入用户名: ").strip()
        if not username:
            print("❌ 用户名不能为空")
            return
        
        try:
            max_pages = int(input("请输入最大页数(默认3): ") or "3")
        except ValueError:
            max_pages = 3
        
        print(f"\n🔍 开始爬取用户 {username} 的视频...")
        videos = self.scraper.get_user_videos(username, max_pages)
        
        if videos:
            print(f"\n✅ 成功爬取 {len(videos)} 个视频")
            print("\n" + "="*80)
            for i, video in enumerate(videos, 1):
                print(f"{i}. {video['title']}")
                print(f"   时长: {video.get('upload_time', '未知')}")
                print(f"   链接: {video['url']}")
                if video.get('thumbnail'):
                    print(f"   缩略图: {video['thumbnail']}")
                print("-" * 80)
        else:
            print("❌ 没有找到视频，请检查用户名是否正确")
    
    def test_connection(self):
        """测试网络连接"""
        print("\n🌐 正在测试网络连接...")
        if self.scraper.test_connection():
            print("✅ 网络连接正常，可以开始爬取")
        else:
            print("❌ 网络连接失败，请检查网络设置")
    
    def show_instructions(self):
        """显示使用说明"""
        print("\n📖 使用说明:")
        print("1. 确保平板已连接网络")
        print("2. 输入hsex.men上的用户名（不是完整URL）")
        print("3. 例如: 如果URL是 https://hsex.men/author/testuser")
        print("   只需输入: testuser")
        print("4. 建议从少量页数开始测试")
        print("5. 如遇网络问题，可尝试切换网络环境")

if __name__ == '__main__':
    try:
        # 确保在Pydroid 3中运行
        if 'ANDROID_ARGUMENT' in os.environ:
            print("📱 检测到Android环境")
        
        app = MobileApp()
        app.run()
    except KeyboardInterrupt:
        print("\n\n👋 用户中断，程序退出")
    except Exception as e:
        print(f"\n❌ 程序运行出错: {str(e)}")
        logger.exception("程序异常")