# 数据库设置
DATABASE_FILE = 'video_updates.db'

# 默认设置
DEFAULT_CHECK_INTERVAL = 3600  # 1小时
DEFAULT_UPDATE_RANGE_DAYS = 7  # 7天
DEFAULT_AUTO_CHECK = True

# 网络请求设置
REQUEST_TIMEOUT = 10  # 秒
REQUEST_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

# UI设置
WINDOW_MIN_WIDTH = 1200
WINDOW_MIN_HEIGHT = 800
THUMBNAIL_WIDTH = 160
THUMBNAIL_HEIGHT = 90
AVATAR_SIZE = 40

# 日志设置
LOG_DIR = 'logs'
LOG_FILE = 'app.log'
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
LOG_LEVEL = 'INFO'

# 缓存设置
CACHE_DIR = 'cache'
IMAGE_CACHE_DIR = 'cache/images'
MAX_CACHE_AGE = 86400  # 24小时

# 并发与缓存
MAX_WORKERS = 6
PAGE_CACHE_TTL = 300
DOMAIN_MAX_CONCURRENCY = 2
IMAGE_LOAD_CONCURRENCY = 4

# 视频相关
VIDEO_URL_PATTERN = r'video/(\d+)'
RELATIVE_TIME_PATTERNS = {
    'days': r'(\d+)\s*天前',
    'months': r'(\d+)\s*个?月前',
    'years': r'(\d+)\s*年前'
} 
