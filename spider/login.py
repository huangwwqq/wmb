"""登录。POST /async/sign，账号密码明文表单，成功 state=0，cookie 在响应里。"""
import sys
sys.path.append('../')
from curl_cffi import requests as creq
from setting.setting import *


class LoginTool:

    def login(self, username: str, password: str):
        session = creq.Session(impersonate='chrome131')
        session.headers.update(HEADER)
        try:
            session.get(BASE_URL + '/', timeout=60)
            response = session.post(
                BASE_URL + '/async/sign',
                data={'user_name': username, 'password': password},
                timeout=60,
            )
        except Exception as exc:
            logger.warning(f'登录请求失败: {exc}')
            return 0, {}
        try:
            payload = response.json()
        except Exception:
            logger.warning(f'登录返回不是 JSON: {response.status_code} {(response.text or "")[:200]}')
            return 0, {}
        if payload.get('state') != 0:
            logger.warning(f'登录失败: {payload.get("message") or payload}')
            return 0, {}
        cookies = session.cookies.get_dict()
        if not cookies:
            logger.warning('登录成功但没有 cookie')
            return 0, {}
        logger.info(f'登录成功: {username}')
        return 1, cookies
