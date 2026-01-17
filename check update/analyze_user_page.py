#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分析用户页面HTML结构
用于找到正确的视频选择器
"""

import requests
from bs4 import BeautifulSoup
import re
import json

def analyze_user_page():
    """分析用户页面的视频结构"""
    print("🔍 分析用户页面视频结构...")
    
    # 测试URL
    test_url = "https://hsex.men/user.htm?author=345061255"
    
    # 设置请求头
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Accept-Encoding': 'identity',  # 禁用压缩
        'Connection': 'keep-alive',
    }
    
    try:
        print(f"📡 获取页面: {test_url}")
        response = requests.get(test_url, headers=headers, timeout=10)
        
        print(f"📊 状态码: {response.status_code}")
        print(f"📊 内容长度: {len(response.content)} 字节")
        print(f"📊 编码: {response.encoding}")
        print(f"📊 内容类型: {response.headers.get('content-type', 'unknown')}")
        
        # 直接使用response.text，requests会自动处理编码
        html = response.text
        
        # 保存原始HTML
        with open('user_page.html', 'w', encoding='utf-8') as f:
            f.write(html)
        print("📄 HTML已保存到 user_page.html")
        
        # 解析HTML
        soup = BeautifulSoup(html, 'lxml')
        
        print(f"\n📊 页面基本信息:")
        print(f"   标题: {soup.title.string if soup.title else '无标题'}")
        print(f"   所有标签: {len(soup.find_all())}")
        print(f"   div标签: {len(soup.find_all('div'))}")
        print(f"   a标签: {len(soup.find_all('a'))}")
        print(f"   img标签: {len(soup.find_all('img'))}")
        
        # 查找可能的视频容器
        print(f"\n🔍 查找视频容器...")
        
        # 查找所有可能的视频相关元素
        video_patterns = [
            # 通过class查找
            'div[class*="video"]',
            'div[class*="item"]',
            'div[class*="content"]',
            'div[class*="card"]',
            'div[class*="box"]',
            'div[class*="list"]',
            
            # 具体class名称
            '.video-item',
            '.item',
            '.content-item',
            '.card',
            '.video-card',
            '.video-box',
            '.video-list-item',
            '.gallery-item',
            '.thumb-item',
            
            # 通过ID查找
            'div[id*="video"]',
            'div[id*="item"]',
            
            # 通过属性查找
            'div[data-id]',
            'div[data-video]',
        ]
        
        found_containers = []
        for pattern in video_patterns:
            elements = soup.select(pattern)
            if elements:
                found_containers.append({
                    'selector': pattern,
                    'count': len(elements),
                    'elements': elements[:3]  # 保存前3个用于分析
                })
                print(f"   ✅ {pattern}: {len(elements)} 个元素")
        
        # 分析找到的元素结构
        print(f"\n📋 分析元素结构...")
        for container in found_containers:
            print(f"\n📊 选择器: {container['selector']} ({container['count']}个)")
            for i, elem in enumerate(container['elements']):
                print(f"   元素 {i+1}:")
                print(f"      标签: {elem.name}")
                print(f"      class: {elem.get('class', [])}")
                print(f"      id: {elem.get('id', '无')}")
                
                # 查找子元素中的链接和图片
                links = elem.find_all('a', href=True)
                imgs = elem.find_all('img', src=True)
                
                if links:
                    print(f"      链接: {len(links)} 个")
                    for link in links[:2]:
                        print(f"         href: {link['href']}")
                        print(f"         text: {link.get_text(strip=True)[:50]}")
                
                if imgs:
                    print(f"      图片: {len(imgs)} 个")
                    for img in imgs[:2]:
                        print(f"         src: {img['src']}")
                        print(f"         alt: {img.get('alt', '无alt')}")
        
        # 查找特定的视频链接模式
        print(f"\n🔗 查找视频链接...")
        video_links = soup.find_all('a', href=re.compile(r'video|watch|play|view'))
        print(f"   找到 {len(video_links)} 个可能的视频链接")
        
        for i, link in enumerate(video_links[:5]):
            print(f"   {i+1}. href: {link.get('href', '无')}")
            print(f"      text: {link.get_text(strip=True)[:50]}")
            print(f"      parent class: {link.parent.get('class', []) if link.parent else '无'}")
        
        # 查找图片链接
        print(f"\n🖼️ 查找图片...")
        images = soup.find_all('img', src=True)
        print(f"   找到 {len(images)} 张图片")
        
        # 过滤可能的视频缩略图
        video_thumbnails = []
        for img in images:
            src = img.get('src', '')
            if any(ext in src.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif']):
                video_thumbnails.append({
                    'src': src,
                    'alt': img.get('alt', ''),
                    'parent': img.parent.name if img.parent else None
                })
        
        print(f"   找到 {len(video_thumbnails)} 张可能的视频缩略图")
        for i, img in enumerate(video_thumbnails[:5]):
            print(f"   {i+1}. src: {img['src']}")
            print(f"      alt: {img['alt']}")
        
        # 查找所有div并分析其结构
        print(f"\n📋 分析所有div结构...")
        all_divs = soup.find_all('div')
        
        # 统计class出现频率
        class_counts = {}
        for div in all_divs:
            classes = div.get('class', [])
            for cls in classes:
                class_counts[cls] = class_counts.get(cls, 0) + 1
        
        # 显示最常见的class
        sorted_classes = sorted(class_counts.items(), key=lambda x: x[1], reverse=True)
        print("   最常见的div class:")
        for cls, count in sorted_classes[:15]:
            print(f"      {cls}: {count}次")
        
        # 尝试提取视频信息
        print(f"\n🎯 尝试提取视频信息...")
        
        # 根据实际页面结构提取
        videos = []
        
        # 方法1: 查找包含视频链接的容器
        # 先查找所有包含/video/的链接
        video_links = soup.find_all('a', href=re.compile(r'/video/\d+'))
        print(f"   找到 {len(video_links)} 个视频链接")
        
        for link in video_links:
            video_info = {}
            
            # 提取视频ID
            href = link.get('href', '')
            match = re.search(r'/video/(\d+)', href)
            if match:
                video_info['video_id'] = match.group(1)
            
            # 查找容器（向上查找最近的div）
            container = link.find_parent('div')
            if container:
                # 在容器内查找标题
                title_elem = (container.find('a', title=True) or 
                            container.find('h3') or 
                            container.find('div', class_=re.compile(r'title')) or
                            container.find('span', class_=re.compile(r'title')) or
                            link)
                
                if title_elem:
                    video_info['title'] = title_elem.get_text(strip=True)
                
                # 查找缩略图
                img_elem = container.find('img', src=True)
                if img_elem:
                    video_info['thumbnail'] = img_elem['src']
                
                # 查找时长
                duration_elem = container.find('span', class_=re.compile(r'time|duration'))
                if duration_elem:
                    video_info['duration'] = duration_elem.get_text(strip=True)
            
            if video_info:
                videos.append(video_info)
        
        # 方法2: 查找具有特定class的div
        # 根据最常见的class尝试
        likely_classes = [cls for cls, count in sorted_classes if count > 1][:5]
        
        for cls in likely_classes:
            elements = soup.find_all('div', class_=cls)
            for elem in elements:
                # 检查是否包含视频相关元素
                video_link = elem.find('a', href=re.compile(r'/video/\d+'))
                if video_link:
                    video_info = {}
                    
                    # 提取视频ID
                    match = re.search(r'/video/(\d+)', video_link['href'])
                    if match:
                        video_info['video_id'] = match.group(1)
                    
                    # 提取标题
                    title_elem = elem.find('a', title=True) or elem.find('h3')
                    if title_elem:
                        video_info['title'] = title_elem.get_text(strip=True)
                    
                    # 提取缩略图
                    img_elem = elem.find('img')
                    if img_elem:
                        video_info['thumbnail'] = img_elem['src']
                    
                    # 避免重复
                    if video_info and video_info not in videos:
                        videos.append(video_info)
        
        print(f"   提取到 {len(videos)} 个视频信息")
        for i, video in enumerate(videos[:5]):
            print(f"   {i+1}. 标题: {video.get('title', '无标题')}")
            print(f"      ID: {video.get('video_id', '无ID')}")
            print(f"      缩略图: {video.get('thumbnail', '无缩略图')}")
            print(f"      时长: {video.get('duration', '无时长')}")
        
        return found_containers, videos
        
    except Exception as e:
        print(f"❌ 分析出错: {e}")
        import traceback
        traceback.print_exc()
        return None, None

def create_updated_selectors():
    """基于分析结果创建更新的选择器"""
    print("\n" + "="*60)
    print("🔄 创建更新的选择器...")
    
    try:
        with open('user_page.html', 'r', encoding='utf-8') as f:
            html = f.read()
        
        soup = BeautifulSoup(html, 'lxml')
        
        # 基于实际页面结构的选择器
        updated_selectors = [
            'div.video-item',
            'div.item',
            'div.content-item',
            'div[class*="video-item"]',
            'div[class*="video-box"]',
            'a[href*="/video/"]',
            'div[class*="list"] > div',
            'div[data-video-id]',
        ]
        
        print("   建议的更新选择器:")
        for selector in updated_selectors:
            elements = soup.select(selector)
            if elements:
                print(f"   ✅ {selector}: {len(elements)} 个元素")
            else:
                print(f"   ❌ {selector}: 未找到")
        
        return updated_selectors
        
    except FileNotFoundError:
        print("   ❌ 请先运行 analyze_user_page()")
        return []

if __name__ == "__main__":
    containers, videos = analyze_user_page()
    selectors = create_updated_selectors()
    
    print("\n" + "="*60)
    print("💡 分析完成！")
    print("📁 查看 user_page.html 了解页面结构")
    print("🔍 根据分析结果更新解析选择器")
    print("="*60)