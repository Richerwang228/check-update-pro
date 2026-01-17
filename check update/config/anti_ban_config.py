"""
反爬虫配置
用于调整网络请求的各种参数以绕过反爬机制
"""

class AntiBanConfig:
    """反爬配置类"""
    
    # 请求间隔配置
    MIN_INTERVAL = 2  # 最小请求间隔（秒）
    MAX_INTERVAL = 15   # 最大请求间隔（秒）
    FAILURE_PENALTY = 2  # 失败惩罚倍数
    
    # 重试配置
    MAX_RETRIES = 5   # 最大重试次数
    RETRY_BACKOFF = 2  # 重试退避倍数
    
    # 超时配置
    CONNECT_TIMEOUT = 10  # 连接超时（秒）
    READ_TIMEOUT = 30    # 读取超时（秒）
    
    # 代理配置
    # ⚠️ 重要：以下代理IP已失效，请替换为实际可用的付费代理
    PROXY_POOL = [
        None,  # 直连优先 - 大多数情况下直连更快
        # 以下是付费代理服务示例（需要注册账号）
        # {'http': 'http://username:password@proxy-service.com:port', 'https': 'http://username:password@proxy-service.com:port'},
    ]
    
    # 代理服务推荐（请注册付费账号）
    RECOMMENDED_PROXIES = {
        'bright_data': 'https://brightdata.com - 住宅IP，质量最高',
        'oxylabs': 'https://oxylabs.io - 企业级代理',
        'smartproxy': 'https://smartproxy.com - 性价比高',
        'proxy_cheap': 'https://proxy-cheap.com - 便宜选择',
    }
    
    # User-Agent池
    USER_AGENTS = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36',
    ]
    
    # 请求头配置
    HEADERS = {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Cache-Control': 'max-age=0',
        'Upgrade-Insecure-Requests': '1',
        'sec-ch-ua': '"Chromium";v="128", "Not;A=Brand";v="24", "Google Chrome";v="128"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'document',
        'sec-fetch-mode': 'navigate',
        'sec-fetch-site': 'none',
        'sec-fetch-user': '?1',
        'DNT': '1',
        'Priority': 'u=0, i'
    }
    
    # 目标网站特定配置
    TARGET_SITES = {
        'hsex.men': {
            'referer': 'https://hsex.men/',
            'cookies': {
                'PHPSESSID': None,  # 动态生成
                'cf_clearance': None,  # 动态生成
                '__cf_bm': None,  # 动态生成
                '_ga': None,  # 动态生成
                '_gid': None,  # 动态生成
                '_gat': '1',
                'timezone': 'Asia/Shanghai',
                'language': 'zh-CN'
            }
        }
    }