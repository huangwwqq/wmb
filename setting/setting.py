import logging
import os
import sys
from concurrent_log_handler import ConcurrentRotatingFileHandler

ROOT_PATH = os.path.dirname(os.path.dirname(__file__))
sys.path.append(ROOT_PATH)
LOGDIRPATH = os.path.join(ROOT_PATH, 'logs').replace('\\', '/')
if os.path.exists(LOGDIRPATH) is False:
    os.makedirs(LOGDIRPATH)

logger = logging.getLogger('wmb_info')
logger.setLevel(logging.INFO)
logger.propagate = False
if not logger.handlers:
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler = ConcurrentRotatingFileHandler(
        os.path.join(LOGDIRPATH, 'wmb_info.log'),
        maxBytes=50 * 1024 * 1024,
        backupCount=5,
        encoding='utf-8',
    )
    handler.setLevel(logging.INFO)
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    console.setLevel(logging.INFO)
    logger.addHandler(console)

# 只留实测能稳定返回的指纹。随机到旧指纹时，公司页会一直挂住。
BrowserTypeLiteral = [
    "chrome131",
]

HEADER = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0',
    'Accept': 'application/json, text/javascript, */*; q=0.01',
    'X-Requested-With': 'XMLHttpRequest',
    'Referer': 'https://www.52wmb.com/buyer',
}

BASE_URL = 'https://www.52wmb.com'
# 站点 company_type：0 采购商，1 供应商。入库 type：1 采购商，2 供应商
SITE_BUYER = 0
SITE_SUPPLIER = 1
DB_BUYER = 1
DB_SUPPLIER = 2

# 生产者数量和翻页都只要「包含邮箱」。国家数量接口是 /async/common/country/stats
FILTER_WEIGHT = 'email'
SEARCH_PAGE_SIZE = 30
TRADE_PAGE_SIZE = 20
# 列表接口单次窗口最多展示约 10000 条，到顶就停，不算失败
SEARCH_MAX = 10000
DETAIL_PAGE_SIZE = 3000

# redis。db 用 2，避开小满的 db 1
REDISHOST = '127.0.0.1'
REDISPORT = 6379
REDISDB = 2
REDISPASSWORD = 'qY2ifGgIHTMhhQbLg3rrmRPepYOZt9ri'
REDISSERVERNAME = 'wmb_user_data'
REDISUSERQUEUE = 'wmb_username_queue'
REDISUSERWAITQUEUE = 'wmb_username_wait_queue'
WAITTIME = 1
LOGINITERVAL = 60 * 60
MAXCHECKUSERDATANUMBER = 30

# PostgreSQL：自建 Supabase 本机 5433，库 postgres
PGHOST = '127.0.0.1'
PGPORT = 5433
PGDATABASE = 'postgres'
PGUSER = 'haitunzhixun'
PGPASSWORD = 'htzxai159!'

SOURCE = 'wmb'
COMPANY_THREADS = 3
CONSUMERSLEEPTIME = 5
PRODUCERSLEEPTIME = 10
BLOCK_SLEEP = 60

# 临时脚本：按产品词搜采购商
CARBON_KEYWORD = 'Carbon fiber'
CARBON_TABLE = 'carbon_fiber_companies'
CARBON_INTERVAL = 1
