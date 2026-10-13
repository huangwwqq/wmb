"""临时脚本：按产品词 Carbon fiber 搜采购商，不进公司任务表，也不走账号队列。

每抓完一家至少间隔 1 秒。公司写入 public.carbon_fiber_companies，提单写入 customs.trade_info。
在 spider/ 下运行: python -u tmp_carbon_fiber.py
"""
import sys
import time
sys.path.append('../')
sys.path = list(set(sys.path))
from account import Account
from curd.tb_company_info import TBCompanyInfo
from curd.tb_trade_info import TBTradeInfo
from login import LoginTool
from setting.setting import *
from wmb_api import WmbApi, WmbBlocked, WmbLogin


def _login_cookie() -> dict:
    item = Account.account_list[0]
    tool = LoginTool()
    for _ in range(3):
        code, cookies = tool.login(item['username'], item['password'])
        if code == 1 and cookies:
            return cookies
        time.sleep(3)
    raise SystemExit('登录失败')


def main():
    cookies = {'cookie': _login_cookie()}

    def getter():
        return cookies['cookie']

    api = WmbApi(getter, gap=0.3)
    company_db = TBCompanyInfo(CARBON_TABLE)
    trade_db = TBTradeInfo()
    start = 0
    done = 0
    logger.info(f'开始按产品词抓采购商: {CARBON_KEYWORD}')
    while start < SEARCH_MAX:
        try:
            hits, rows = api.search_companies(
                company_type=SITE_BUYER,
                country='*',
                start=start,
                key=CARBON_KEYWORD,
                search_type=2,
                filter_weight='default',
            )
        except (WmbBlocked, WmbLogin) as exc:
            logger.warning(f'搜索被拦住,重试: {exc}')
            time.sleep(BLOCK_SLEEP)
            cookies['cookie'] = _login_cookie()
            continue
        logger.info(f'Carbon fiber start={start} 本页{len(rows)} hits={hits}')
        if not rows:
            break
        for item in rows:
            company_id = item.get('id')
            if not company_id:
                continue
            try:
                fetched = api.fetch_company(company_id, DB_BUYER)
            except (WmbBlocked, WmbLogin) as exc:
                logger.warning(f'{company_id} 被拦住,稍后重试: {exc}')
                time.sleep(BLOCK_SLEEP)
                cookies['cookie'] = _login_cookie()
                try:
                    fetched = api.fetch_company(company_id, DB_BUYER)
                except Exception as again:
                    logger.warning(f'{company_id} 仍然失败: {again}')
                    time.sleep(CARBON_INTERVAL)
                    continue
            except Exception as exc:
                logger.warning(f'{company_id} 抓取失败: {exc}')
                time.sleep(CARBON_INTERVAL)
                continue
            if fetched:
                company, trades = fetched
                company_db.save_info_data([company])
                trade_db.save_info_data(trades)
                done += 1
                logger.info(f'碳纤维入库 {company_id} 提单{len(trades)} 累计{done}')
            time.sleep(CARBON_INTERVAL)
        if len(rows) < SEARCH_PAGE_SIZE:
            break
        start += SEARCH_PAGE_SIZE
        if hits and start >= min(hits, SEARCH_MAX):
            break
    logger.info(f'碳纤维抓取结束,公司{done}')


if __name__ == '__main__':
    main()
