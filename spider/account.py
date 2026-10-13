"""账号登录，cookie 放进 redis，定时重登。"""
import json
import sys
import time
from datetime import datetime, timedelta, timezone
sys.path.append('../')
sys.path = list(set(sys.path))
from curd.redis_object import RedisObj
from login import LoginTool
from apscheduler.schedulers.blocking import BlockingScheduler
from setting.setting import *

CST = timezone(timedelta(hours=8))


class Account:
    account_list = [
        {'username': '13318158879', 'password': 'Aa3572468@#$'},
    ]

    def __init__(self):
        self.redis_obj = RedisObj()
        self.login_tool = LoginTool()

    def save_login_data(self):
        accounts = [a for a in self.account_list if a and a.get('username') and a.get('password')]
        for item in accounts:
            username = item['username']
            for _ in range(3):
                code, cookies = self.login_tool.login(username=username, password=item['password'])
                if code != 1 or not cookies or not cookies.get('access_token'):
                    logger.warning(f'{username} 登录没有拿到 cookie,跳过,等下一次')
                    time.sleep(3)
                    continue
                redis_save_key = f'{REDISSERVERNAME}_{username}'
                account_data = {
                    'username': username,
                    'password': item['password'],
                    'cookie': json.dumps(cookies),
                }
                self.redis_obj.redis_set_data(key_name=redis_save_key, data=json.dumps(account_data))
                self.redis_obj.zadd(key_name=REDISUSERQUEUE, data={redis_save_key: int(time.time())})
                break


if __name__ == '__main__':
    account = Account()
    scheduler = BlockingScheduler(timezone='Asia/Shanghai')
    scheduler.add_job(
        account.save_login_data,
        'interval',
        seconds=LOGINITERVAL,
        id='wmb_login',
        next_run_time=datetime.now(CST),
        max_instances=1,
        coalesce=True,
        misfire_grace_time=3600,
    )
    logger.info(f'登录调度已启动: 立即执行一次,之后每{LOGINITERVAL}秒')
    scheduler.start()
