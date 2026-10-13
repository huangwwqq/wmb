import random

from curl_cffi import requests as creq
from setting.setting import *


def random_impersonate() -> str:
    """从 BrowserTypeLiteral 随机取 curl_cffi 浏览器指纹。"""
    return random.choice(BrowserTypeLiteral)


def request_get(url, headers=None, proxies=None, params=None, cookies=None, allow_redirects=True):
    reset = 3
    while reset:
        reset -= 1
        try:
            response = creq.get(
                url,
                headers=headers,
                params=params,
                proxies=proxies,
                cookies=cookies,
                allow_redirects=allow_redirects,
                timeout=300,
                impersonate=random_impersonate(),
            )
        except Exception as e:
            logger.error(f'请求异常,异常为{e}')
        else:
            return response
    return


def request_post(url, headers=None, data=None, proxies=None, cookies=None):
    reset = 3
    while reset:
        reset -= 1
        try:
            response = creq.post(
                url,
                headers=headers,
                proxies=proxies,
                data=data,
                cookies=cookies,
                timeout=300,
                impersonate=random_impersonate(),
            )
        except Exception as e:
            logger.error(f'请求异常,异常为{e}')
        else:
            return response
    return
