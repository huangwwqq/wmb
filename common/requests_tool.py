import random
import time

import redis
from curl_cffi import requests as creq
from setting.setting import *

# 同一个账号同时打太多请求时，后面的翻页会回未登录的空对象 {}。所有请求串行。
_redis = None


def _redis_client():
    global _redis
    if _redis is None:
        _redis = redis.Redis(
            host=REDISHOST,
            port=REDISPORT,
            db=REDISDB,
            password=REDISPASSWORD,
            socket_timeout=5,
        )
    return _redis


def hold_http():
    client = _redis_client()
    while True:
        try:
            if client.set('wmb_http_lock', '1', nx=True, ex=90):
                return client
        except Exception as exc:
            logger.warning(f'请求锁失败,稍后重试: {exc}')
        time.sleep(0.3)


def release_http(client):
    try:
        client.delete('wmb_http_lock')
    except Exception:
        pass


def random_impersonate() -> str:
    """从 BrowserTypeLiteral 随机取 curl_cffi 浏览器指纹。"""
    return random.choice(BrowserTypeLiteral)


def request_get(url, headers=None, proxies=None, params=None, cookies=None, allow_redirects=True):
    reset = 3
    while reset:
        reset -= 1
        lock = hold_http()
        try:
            response = creq.get(
                url,
                headers=headers,
                params=params,
                proxies=proxies,
                cookies=cookies,
                allow_redirects=allow_redirects,
                timeout=45,
                impersonate=random_impersonate(),
            )
        except Exception as e:
            logger.error(f'请求异常,异常为{e}')
            time.sleep(2)
        else:
            return response
        finally:
            release_http(lock)
    return


def request_post(url, headers=None, data=None, proxies=None, cookies=None):
    reset = 3
    while reset:
        reset -= 1
        lock = hold_http()
        try:
            response = creq.post(
                url,
                headers=headers,
                proxies=proxies,
                data=data,
                cookies=cookies,
                timeout=45,
                impersonate=random_impersonate(),
            )
        except Exception as e:
            logger.error(f'请求异常,异常为{e}')
            time.sleep(2)
        else:
            return response
        finally:
            release_http(lock)
    return
