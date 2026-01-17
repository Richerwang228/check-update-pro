"""
全局请求管理器
实现请求队列、速率限制、智能重试等功能
"""

import time
import logging
import threading
from collections import deque
from datetime import datetime, timedelta
import random
from config.settings import DOMAIN_MAX_CONCURRENCY

class RequestManager:
    """全局请求管理器 - 单例模式"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized'):
            return
        
        self._initialized = True
        self.logger = logging.getLogger(__name__)
        
        # 请求队列
        self.request_queue = deque()
        self.queue_lock = threading.Lock()
        
        # 速率限制配置（优化为更宽松）
        self.global_rate_limit = 30  # 每分钟最多30个请求（原10→30）
        self.request_history = deque(maxlen=100)  # 记录最近100个请求
        
        # 域名级别的速率控制
        self.domain_last_request = {}
        self.domain_min_interval = 1.0  # 同一域名最小间隔1秒（原3→1）
        
        # 失败统计
        self.failure_count = {}
        self.blocked_until = {}
        
        # 全局统计
        self.total_requests = 0
        self.total_failures = 0
        self.total_blocks = 0
        self.domain_current_concurrency = {}
        self.domain_max_concurrency = DOMAIN_MAX_CONCURRENCY
    
    def should_wait(self, domain: str) -> float:
        """
        检查是否需要等待，返回需要等待的秒数
        """
        now = time.time()
        
        # 1. 检查该域名是否被暂时封禁
        if domain in self.blocked_until:
            if now < self.blocked_until[domain]:
                wait_time = self.blocked_until[domain] - now
                self.logger.warning(f"域名 {domain} 被暂时封禁，需等待 {wait_time:.1f} 秒")
                return wait_time
            else:
                # 封禁时间已过，解除封禁
                del self.blocked_until[domain]
        
        # 2. 检查全局速率限制（滑动窗口）
        recent_requests = [t for t in self.request_history if now - t < 60]
        if len(recent_requests) >= self.global_rate_limit:
            oldest = min(recent_requests)
            wait_time = 60 - (now - oldest) + random.uniform(1, 3)
            self.logger.warning(f"全局速率限制，需等待 {wait_time:.1f} 秒")
            return wait_time
        
        # 3. 检查域名级别的最小间隔
        if domain in self.domain_last_request:
            elapsed = now - self.domain_last_request[domain]
            if elapsed < self.domain_min_interval:
                wait_time = self.domain_min_interval - elapsed + random.uniform(0.5, 1.5)
                return wait_time
        
        return 0
    
    def wait_if_needed(self, domain: str):
        """如果需要，等待适当的时间"""
        wait_time = self.should_wait(domain)
        if wait_time > 0:
            self.logger.info(f"等待 {wait_time:.1f} 秒后再请求 {domain}")
            time.sleep(wait_time)

    def enter_request(self, domain: str):
        while True:
            with self.queue_lock:
                current = self.domain_current_concurrency.get(domain, 0)
                if current < self.domain_max_concurrency:
                    self.domain_current_concurrency[domain] = current + 1
                    return
            time.sleep(0.2)

    def exit_request(self, domain: str):
        with self.queue_lock:
            current = self.domain_current_concurrency.get(domain, 0)
            if current > 0:
                self.domain_current_concurrency[domain] = current - 1
    
    def record_request(self, domain: str, success: bool):
        """记录请求结果"""
        now = time.time()
        
        with self.queue_lock:
            self.total_requests += 1
            self.request_history.append(now)
            self.domain_last_request[domain] = now
            
            if not success:
                self.total_failures += 1
                
                # 记录失败次数
                if domain not in self.failure_count:
                    self.failure_count[domain] = 0
                self.failure_count[domain] += 1
                
                # 如果连续失败，增加封禁时间
                failures = self.failure_count[domain]
                if failures >= 3:
                    # 指数退避：3次=30秒，4次=60秒，5次=120秒
                    block_time = min(30 * (2 ** (failures - 3)), 300)  # 最多5分钟
                    self.blocked_until[domain] = now + block_time
                    self.total_blocks += 1
                    self.logger.error(
                        f"域名 {domain} 连续失败 {failures} 次，"
                        f"封禁 {block_time} 秒"
                    )
            else:
                # 成功后重置失败计数
                if domain in self.failure_count:
                    self.failure_count[domain] = max(0, self.failure_count[domain] - 1)
    
    def get_retry_delay(self, domain: str, attempt: int) -> float:
        """
        获取重试延迟（指数退避）
        attempt: 第几次重试（0为首次）
        """
        base_delay = 2.0
        max_delay = 60.0
        
        # 检查域名的失败历史
        failures = self.failure_count.get(domain, 0)
        
        # 指数退避：2^attempt * base_delay，加上抖动
        delay = min(base_delay * (2 ** attempt) * (1 + failures * 0.5), max_delay)
        jitter = random.uniform(0, delay * 0.3)  # 30%的抖动
        
        return delay + jitter
    
    def get_statistics(self) -> dict:
        """获取统计信息"""
        now = time.time()
        recent_requests = len([t for t in self.request_history if now - t < 60])
        
        return {
            'total_requests': self.total_requests,
            'total_failures': self.total_failures,
            'total_blocks': self.total_blocks,
            'recent_requests_per_minute': recent_requests,
            'active_blocks': len([d for d, t in self.blocked_until.items() if now < t]),
            'domains_tracked': len(self.domain_last_request)
        }
    
    def reset_domain(self, domain: str):
        """重置某个域名的统计（用于测试或手动解封）"""
        with self.queue_lock:
            if domain in self.failure_count:
                del self.failure_count[domain]
            if domain in self.blocked_until:
                del self.blocked_until[domain]
            self.logger.info(f"已重置域名 {domain} 的统计")

# 全局单例
request_manager = RequestManager()
