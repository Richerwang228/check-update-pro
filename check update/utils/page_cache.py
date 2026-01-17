"""
页面缓存系统
缓存HTML页面，避免重复请求
"""

import os
import time
import hashlib
import pickle
import logging
from typing import Optional, Tuple
from datetime import datetime, timedelta

class PageCache:
    """页面缓存管理器"""
    
    def __init__(self, cache_dir='cache/pages', max_age_seconds=300):
        """
        初始化页面缓存
        
        Args:
            cache_dir: 缓存目录
            max_age_seconds: 缓存最大有效期（秒），默认5分钟
        """
        self.cache_dir = cache_dir
        self.max_age = max_age_seconds
        self.logger = logging.getLogger(__name__)
        self._ensure_cache_dir()
        
        # 内存缓存（提升性能）
        self._memory_cache = {}
        self._memory_cache_time = {}
        self.memory_cache_limit = 50  # 最多缓存50个页面在内存
    
    def _ensure_cache_dir(self):
        """确保缓存目录存在"""
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)
    
    def _get_cache_key(self, url: str) -> str:
        """生成缓存键（URL的MD5）"""
        return hashlib.md5(url.encode()).hexdigest()
    
    def _get_cache_path(self, cache_key: str) -> str:
        """获取缓存文件路径"""
        return os.path.join(self.cache_dir, f"{cache_key}.cache")
    
    def get(self, url: str) -> Optional[str]:
        """
        从缓存获取页面
        
        Args:
            url: 页面URL
            
        Returns:
            缓存的HTML内容，如果不存在或过期则返回None
        """
        cache_key = self._get_cache_key(url)
        
        # 1. 尝试从内存缓存获取
        if cache_key in self._memory_cache:
            cache_time = self._memory_cache_time.get(cache_key, 0)
            if time.time() - cache_time < self.max_age:
                self.logger.debug(f"从内存缓存命中: {url[:50]}...")
                return self._memory_cache[cache_key]
            else:
                # 过期，清除内存缓存
                del self._memory_cache[cache_key]
                del self._memory_cache_time[cache_key]
        
        # 2. 尝试从磁盘缓存获取
        cache_path = self._get_cache_path(cache_key)
        
        if not os.path.exists(cache_path):
            return None
        
        try:
            # 检查文件是否过期
            file_mtime = os.path.getmtime(cache_path)
            if time.time() - file_mtime > self.max_age:
                self.logger.debug(f"缓存过期: {url[:50]}...")
                os.remove(cache_path)
                return None
            
            # 读取缓存
            with open(cache_path, 'rb') as f:
                cache_data = pickle.load(f)
            html = cache_data.get('html')
            
            if html:
                # 更新到内存缓存
                self._update_memory_cache(cache_key, html)
                self.logger.debug(f"从磁盘缓存命中: {url[:50]}...")
                return html
            
        except Exception as e:
            self.logger.error(f"读取缓存失败: {str(e)}")
            # 损坏的缓存文件，删除
            try:
                os.remove(cache_path)
            except:
                pass
        
        return None
    
    def set(self, url: str, html: str, metadata: dict = None):
        """
        保存页面到缓存
        
        Args:
            url: 页面URL
            html: HTML内容
            metadata: 可选的元数据
        """
        if not html:
            return
        
        cache_key = self._get_cache_key(url)
        cache_path = self._get_cache_path(cache_key)
        
        try:
            cache_data = {
                'url': url,
                'html': html,
                'cached_at': time.time(),
                'metadata': metadata or {}
            }
            
            # 保存到磁盘
            with open(cache_path, 'wb') as f:
                pickle.dump(cache_data, f)
            
            # 更新到内存缓存
            self._update_memory_cache(cache_key, html)
            
            self.logger.debug(f"页面已缓存: {url[:50]}...")
            
        except Exception as e:
            self.logger.error(f"保存缓存失败: {str(e)}")

    def get_with_meta(self, url: str) -> Optional[Tuple[str, dict]]:
        cache_key = self._get_cache_key(url)
        cache_path = self._get_cache_path(cache_key)
        if not os.path.exists(cache_path):
            return None
        try:
            file_mtime = os.path.getmtime(cache_path)
            if time.time() - file_mtime > self.max_age:
                os.remove(cache_path)
                return None
            with open(cache_path, 'rb') as f:
                cache_data = pickle.load(f)
            html = cache_data.get('html')
            metadata = cache_data.get('metadata', {})
            if html:
                self._update_memory_cache(cache_key, html)
                return html, metadata
        except Exception:
            try:
                os.remove(cache_path)
            except:
                pass
        return None
    
    def _update_memory_cache(self, cache_key: str, html: str):
        """更新内存缓存，带LRU策略"""
        # 如果内存缓存已满，删除最旧的
        if len(self._memory_cache) >= self.memory_cache_limit:
            oldest_key = min(self._memory_cache_time, key=self._memory_cache_time.get)
            del self._memory_cache[oldest_key]
            del self._memory_cache_time[oldest_key]
        
        self._memory_cache[cache_key] = html
        self._memory_cache_time[cache_key] = time.time()
    
    def invalidate(self, url: str):
        """使某个URL的缓存失效"""
        cache_key = self._get_cache_key(url)
        
        # 从内存删除
        if cache_key in self._memory_cache:
            del self._memory_cache[cache_key]
            del self._memory_cache_time[cache_key]
        
        # 从磁盘删除
        cache_path = self._get_cache_path(cache_key)
        if os.path.exists(cache_path):
            try:
                os.remove(cache_path)
                self.logger.debug(f"缓存已失效: {url[:50]}...")
            except Exception as e:
                self.logger.error(f"删除缓存失败: {str(e)}")
    
    def clear_all(self):
        """清除所有缓存"""
        # 清除内存缓存
        self._memory_cache.clear()
        self._memory_cache_time.clear()
        
        # 清除磁盘缓存
        try:
            for filename in os.listdir(self.cache_dir):
                if filename.endswith('.cache'):
                    file_path = os.path.join(self.cache_dir, filename)
                    os.remove(file_path)
            self.logger.info("所有页面缓存已清除")
        except Exception as e:
            self.logger.error(f"清除缓存失败: {str(e)}")
    
    def clear_expired(self):
        """清除过期的缓存"""
        now = time.time()
        cleared = 0
        
        # 清除内存中过期的
        expired_keys = [
            key for key, cache_time in self._memory_cache_time.items()
            if now - cache_time > self.max_age
        ]
        for key in expired_keys:
            del self._memory_cache[key]
            del self._memory_cache_time[key]
            cleared += 1
        
        # 清除磁盘上过期的
        try:
            for filename in os.listdir(self.cache_dir):
                if filename.endswith('.cache'):
                    file_path = os.path.join(self.cache_dir, filename)
                    if now - os.path.getmtime(file_path) > self.max_age:
                        os.remove(file_path)
                        cleared += 1
        except Exception as e:
            self.logger.error(f"清除过期缓存失败: {str(e)}")
        
        if cleared > 0:
            self.logger.info(f"已清除 {cleared} 个过期缓存")
    
    def get_stats(self) -> dict:
        """获取缓存统计信息"""
        disk_count = 0
        disk_size = 0
        
        try:
            for filename in os.listdir(self.cache_dir):
                if filename.endswith('.cache'):
                    disk_count += 1
                    file_path = os.path.join(self.cache_dir, filename)
                    disk_size += os.path.getsize(file_path)
        except:
            pass
        
        return {
            'memory_cached': len(self._memory_cache),
            'disk_cached': disk_count,
            'disk_size_mb': disk_size / (1024 * 1024),
            'max_age_seconds': self.max_age
        }

# 全局实例
from config.settings import PAGE_CACHE_TTL
page_cache = PageCache(max_age_seconds=PAGE_CACHE_TTL)




