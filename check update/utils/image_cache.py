import os
import hashlib
import time
from typing import Optional
from PIL import Image, ImageDraw
from io import BytesIO
import requests
from PyQt6.QtGui import QPixmap
import logging
from config.settings import IMAGE_CACHE_DIR, MAX_CACHE_AGE

class ImageCache:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._ensure_cache_dir()
    
    def _ensure_cache_dir(self):
        """确保缓存目录存在"""
        if not os.path.exists(IMAGE_CACHE_DIR):
            os.makedirs(IMAGE_CACHE_DIR)
    
    def _get_cache_path(self, url: str) -> str:
        """获取图片的缓存路径"""
        # 使用URL的MD5作为文件名
        filename = hashlib.md5(url.encode()).hexdigest() + '.png'
        return os.path.join(IMAGE_CACHE_DIR, filename)
    
    def _is_cache_valid(self, cache_path: str) -> bool:
        """检查缓存是否有效"""
        if not os.path.exists(cache_path):
            return False
            
        # 检查文件是否过期
        mtime = os.path.getmtime(cache_path)
        return (time.time() - mtime) < MAX_CACHE_AGE
    
    def get_image(self, url: str, make_round: bool = False) -> Optional[QPixmap]:
        """获取图片，优先从缓存加载"""
        try:
            if not url:
                return None
                
            cache_path = self._get_cache_path(url)
            
            # 如果缓存有效，直接返回
            if self._is_cache_valid(cache_path):
                pixmap = QPixmap(cache_path)
                return pixmap if pixmap and not pixmap.isNull() else None
            
            # 下载新图片
            response = requests.get(url)
            image = Image.open(BytesIO(response.content))
            
            if make_round:
                # 创建圆形头像
                mask = Image.new('L', image.size, 0)
                mask_draw = ImageDraw.Draw(mask)
                mask_draw.ellipse((0, 0) + image.size, fill=255)
                output = Image.new('RGBA', image.size, (0, 0, 0, 0))
                output.paste(image, (0, 0))
                output.putalpha(mask)
                image = output
            
            # 保存到缓存
            image.save(cache_path, 'PNG')
            
            # 转换为QPixmap
            pixmap = QPixmap(cache_path)
            return pixmap if not pixmap.isNull() else None
            
        except Exception as e:
            self.logger.error(f"Error loading image from {url}: {str(e)}")
            return None
    
    def clear_expired(self):
        """清理过期的缓存文件"""
        try:
            current_time = time.time()
            for filename in os.listdir(IMAGE_CACHE_DIR):
                file_path = os.path.join(IMAGE_CACHE_DIR, filename)
                if os.path.isfile(file_path):
                    mtime = os.path.getmtime(file_path)
                    if (current_time - mtime) >= MAX_CACHE_AGE:
                        os.remove(file_path)
        except Exception as e:
            self.logger.error(f"Error clearing expired cache: {str(e)}")
    
    def clear_all(self):
        """清理所有缓存文件"""
        try:
            for filename in os.listdir(IMAGE_CACHE_DIR):
                file_path = os.path.join(IMAGE_CACHE_DIR, filename)
                if os.path.isfile(file_path):
                    os.remove(file_path)
        except Exception as e:
            self.logger.error(f"Error clearing all cache: {str(e)}")

# 创建全局实例
image_cache = ImageCache() 