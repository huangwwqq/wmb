"""账号冷却。用完进入等待队列，WAITTIME 秒后再回到使用队列。"""
import json
import sys
import time
sys.path.append('../')
sys.path = list(set(sys.path))
from curd.redis_object import RedisObj
from setting.setting import *


class AccountQueue:

    def __init__(self):
        self.redis_obj = RedisObj()

    def get_login_data(self):
        user_data_list = self.redis_obj.zpopmin(key_name=REDISUSERQUEUE)
        if not user_data_list or not user_data_list[0] or not user_data_list[0][0]:
            return '', {}
        user_data_key = user_data_list[0][0]
        if isinstance(user_data_key, bytes):
            user_data_key = user_data_key.decode()
        account_data = self.redis_obj.get(user_data_key)
        if not account_data:
            return '', {}
        self.redis_obj.zadd(key_name=REDISUSERWAITQUEUE, data={user_data_key: int(time.time())})
        if isinstance(account_data, bytes):
            account_data = account_data.decode()
        data = json.loads(account_data)
        cookie = data.get('cookie')
        if isinstance(cookie, str):
            try:
                cookie = json.loads(cookie)
            except Exception:
                cookie = None
        if not cookie or not cookie.get('access_token'):
            logger.warning('cookie 为空,跳过,等下一次登录')
            return '', {}
        data['cookie'] = cookie
        return user_data_key, data

    def check_user_data(self):
        while True:
            wait_user_data_list = self.redis_obj.zpopmin(
                key_name=REDISUSERWAITQUEUE,
                pop_number=MAXCHECKUSERDATANUMBER,
            )
            if not wait_user_data_list:
                time.sleep(0.3)
                continue
            now_time = int(time.time())
            for user_data_item in wait_user_data_list:
                user_data_key, score = user_data_item
                key = user_data_key.decode() if isinstance(user_data_key, bytes) else user_data_key
                if (now_time - score) >= WAITTIME:
                    self.redis_obj.zadd(key_name=REDISUSERQUEUE, data={key: int(time.time())})
                else:
                    self.redis_obj.zadd(key_name=REDISUSERWAITQUEUE, data={key: score})
            time.sleep(0.3)


if __name__ == '__main__':
    AccountQueue().check_user_data()
