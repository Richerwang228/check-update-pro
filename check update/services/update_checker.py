from datetime import datetime, timedelta
import logging
from typing import List, Dict, Optional
from models.database import Bookmark, Video, Settings
from services.web_scraper import WebScraper
from config.settings import MAX_WORKERS
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

class UpdateChecker:
    def __init__(self, session, max_workers=None):
        self.session = session
        self.scraper = WebScraper()
        self.logger = logging.getLogger(__name__)
        self.max_workers = max_workers or MAX_WORKERS
        self._lock = threading.Lock()
        self._progress_callback = None
        self._item_callback = None
        self._stop_flag = False  # 添加停止标志
        try:
            from sqlalchemy.orm import sessionmaker
            bind = getattr(self.session, 'get_bind', None)
            engine = bind() if callable(bind) else getattr(self.session, 'bind', None)
            if engine is not None:
                self._SessionFactory = sessionmaker(bind=engine)
            else:
                self._SessionFactory = None
        except Exception:
            self._SessionFactory = None

    def stop(self):
        """停止检查"""
        self._stop_flag = True

    def set_progress_callback(self, callback):
        """设置进度回调函数"""
        self._progress_callback = callback

    def set_item_callback(self, callback):
        self._item_callback = callback

    def check_all_bookmarks(self) -> List[Dict]:
        """并发检查所有书签的更新"""
        try:
            settings = self.session.query(Settings).first()
            if not settings:
                self.logger.warning("No settings found, using defaults")
                update_range_days = 7
            else:
                update_range_days = settings.update_range_days

            bookmarks = self.session.query(Bookmark).all()
            all_updates = []
            
            if not bookmarks:
                return all_updates

            # 使用线程池并发检查
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # 提交所有任务
                future_to_bookmark = {}
                for i, bookmark in enumerate(bookmarks):
                    if self._stop_flag:
                        break
                    future = executor.submit(self._check_bookmark_safe, bookmark, update_range_days, i, len(bookmarks))
                    future_to_bookmark[future] = bookmark
                
                # 收集结果
                completed = 0
                for future in as_completed(future_to_bookmark):
                    if self._stop_flag:
                        executor.shutdown(wait=False)
                        break
                        
                    bookmark = future_to_bookmark[future]
                    completed += 1
                    try:
                        updates = future.result()
                        if updates:
                            if self._item_callback:
                                for u in updates:
                                    try:
                                        self._item_callback(u)
                                    except Exception:
                                        pass
                            all_updates.extend(updates)
                        if self._progress_callback:
                            self._progress_callback(completed, len(bookmarks), bookmark.name)
                            
                    except Exception as e:
                        self.logger.error(f"检查书签 {bookmark.url} 失败: {str(e)}")

            # 更新最后检查时间
            if settings:
                with self._lock:
                    settings.last_check_time = datetime.now()
                    self.session.commit()

            return all_updates

        except Exception as e:
            self.logger.error(f"检查更新失败: {str(e)}")
            return []
    
    def _check_bookmark_safe(self, bookmark, update_range_days, index, total):
        """线程安全的检查单个书签（带延迟避免触发速率限制）"""
        if self._stop_flag:
            return []
            
        try:
            # 根据索引添加少量延迟，避免所有请求同时发出
            delay = index * 0.2  # 每个书签间隔0.2秒（原0.5→0.2）
            time.sleep(delay)
            local_scraper = WebScraper()
            return self._check_single_bookmark_with_scraper(local_scraper, bookmark, update_range_days)
        except Exception as e:
            self.logger.error(f"检查书签 {bookmark.url} 出错: {str(e)}")
            return []

    def check_single_bookmark(self, bookmark, update_range_days):
        """
        检查单个书签（修复版：确保不漏检）
        """
        try:
            start_time = datetime.now()
            
            # 获取页面内容（关闭缓存，确保数据最新）
            html = self.scraper.get_page_content(bookmark.url, use_cache=False)
            if not html:
                return []

            # 解析视频信息
            videos = self.scraper.parse_video_info(html, bookmark.url)
            if not videos:
                return []

            # 获取时间范围内的最新视频（使用原始逻辑，确保不漏检）
            cutoff_time = datetime.now() - timedelta(days=update_range_days)
            latest_video = None
            
            for video in videos:
                upload_time = video.get('upload_time')
                if upload_time and upload_time > cutoff_time:
                    if latest_video is None or video['upload_time'] > latest_video['upload_time']:
                        latest_video = video

            # 更新书签统计（简化版）
            bookmark.last_check_time = datetime.now()
            bookmark.check_count = (bookmark.check_count or 0) + 1
            if videos:
                bookmark.last_video_id = videos[0].get('video_id', '')
            self.session.commit()
            
            # 返回结果
            if latest_video:
                elapsed = (datetime.now() - start_time).total_seconds()
                self.logger.info(f"✓ {bookmark.name}: 发现新视频 ({elapsed:.1f}秒)")
                return [{'bookmark': bookmark, 'video': Video(**latest_video)}]
            else:
                self.logger.info(f"○ {bookmark.name}: 无新视频")
                return []

        except Exception as e:
            self.logger.error(f"检查书签更新失败: {str(e)}")
            return []
    
    def _should_check_now(self, bookmark) -> bool:
        """
        根据UP主活跃度判断是否应该现在检查
        """
        # 如果从未检查过，必须检查
        if not bookmark.last_check_time:
            return True
        
        # 计算距上次检查的时间
        time_since_check = datetime.now() - bookmark.last_check_time
        hours_since_check = time_since_check.total_seconds() / 3600
        
        # 根据更新频率动态调整检查间隔
        # 更新频率越低（天数越大），检查间隔越长
        check_interval_hours = bookmark.update_frequency * 24 / 7  # 转换为小时
        
        return hours_since_check >= check_interval_hours
    
    def _get_new_videos(self, bookmark, videos, update_range_days):
        """
        增量检查：获取新视频（相比上次检查）
        """
        cutoff_time = datetime.now() - timedelta(days=update_range_days)
        new_videos = []
        last_video_id = bookmark.last_video_id
        
        for video in videos:
            video_id = video.get('video_id', '')
            upload_time = video.get('upload_time')
            
            # 如果遇到上次检查的最后一个视频，停止
            if last_video_id and video_id == last_video_id:
                self.logger.debug(f"到达上次检查位置: {video_id}")
                break
            
            # 检查是否在时间范围内
            if upload_time and upload_time > cutoff_time:
                new_videos.append(video)
        
        return new_videos
    
    def _update_bookmark_stats(self, bookmark, success: bool, new_videos_count: int):
        """
        更新书签统计信息并智能调整检查频率
        """
        try:
            bookmark.last_check_time = datetime.now()
            bookmark.check_count = (bookmark.check_count or 0) + 1
            
            if success:
                if new_videos_count > 0:
                    # 发现新视频，降低更新频率（更频繁检查）
                    bookmark.consecutive_no_update = 0
                    bookmark.update_frequency = max(1, bookmark.update_frequency - 1)
                    self.logger.debug(f"📈 {bookmark.name} 活跃，调整频率为 {bookmark.update_frequency} 天")
                else:
                    # 没有新视频，增加连续无更新次数
                    bookmark.consecutive_no_update += 1
                    
                    # 连续多次无更新，降低检查频率
                    if bookmark.consecutive_no_update >= 3:
                        bookmark.update_frequency = min(30, bookmark.update_frequency + 2)
                        self.logger.debug(f"📉 {bookmark.name} 不活跃，调整频率为 {bookmark.update_frequency} 天")
            
            self.session.commit()
            
        except Exception as e:
            self.logger.error(f"更新书签统计失败: {str(e)}")

    def _is_within_range(self, upload_time: datetime, days: int) -> bool:
        """检查上传时间是否在指定范围内"""
        try:
            if not upload_time:
                return False
                
            cutoff = datetime.now() - timedelta(days=days)
            
            # 添加调试日志
            self.logger.debug(f"检查时间范围:")
            self.logger.debug(f"上传时间: {upload_time}")
            self.logger.debug(f"截止时间: {cutoff}")
            self.logger.debug(f"范围天数: {days}")
            
            # 确保时间比较的时区一致
            if upload_time.tzinfo:
                upload_time = upload_time.replace(tzinfo=None)
            
            is_within = upload_time >= cutoff
            self.logger.debug(f"是否在范围内: {is_within}")
            
            return is_within
            
        except Exception as e:
            self.logger.error(f"检查时间范围失败: {str(e)}")
            return False

    def _check_single_bookmark_with_scraper(self, scraper, bookmark, update_range_days):
        try:
            start_time = datetime.now()
            html = scraper.get_page_content(bookmark.url, use_cache=False)
            if not html:
                return []
            videos = self.scraper.parse_video_info(html, bookmark.url)
            if not videos:
                return []
            cutoff_time = datetime.now() - timedelta(days=update_range_days)
            latest_video = None
            for video in videos:
                upload_time = video.get('upload_time')
                if upload_time and upload_time > cutoff_time:
                    if latest_video is None or video['upload_time'] > latest_video['upload_time']:
                        latest_video = video
            try:
                if self._SessionFactory:
                    local_sess = self._SessionFactory()
                    try:
                        from models.database import Bookmark as BM
                        bm = local_sess.query(BM).filter_by(id=bookmark.id).first()
                        if bm:
                            bm.last_check_time = datetime.now()
                            bm.check_count = (bm.check_count or 0) + 1
                            if videos:
                                bm.last_video_id = videos[0].get('video_id', '')
                            local_sess.commit()
                    finally:
                        local_sess.close()
                else:
                    bookmark.last_check_time = datetime.now()
                    bookmark.check_count = (bookmark.check_count or 0) + 1
                    if videos:
                        bookmark.last_video_id = videos[0].get('video_id', '')
                    self.session.commit()
            except Exception as e:
                self.logger.error(f"更新书签统计失败(线程会话): {str(e)}")
            if latest_video:
                elapsed = (datetime.now() - start_time).total_seconds()
                self.logger.info(f"✓ {bookmark.name}: 发现新视频 ({elapsed:.1f}秒)")
                return [{'bookmark': bookmark, 'video': Video(**latest_video)}]
            else:
                self.logger.info(f"○ {bookmark.name}: 无新视频")
                return []
        except Exception as e:
            self.logger.error(f"检查书签更新失败: {str(e)}")
            return []

    def mark_as_watched(self, video_id: str) -> bool:
        """将视频标记为已看"""
        try:
            video = self.session.query(Video).filter_by(video_id=video_id).first()
            if video:
                video.is_watched = True
                video.watched_at = datetime.now()
                self.session.commit()
                return True
            return False
        except Exception as e:
            self.logger.error(f"Error marking video {video_id} as watched: {str(e)}")
            return False 
