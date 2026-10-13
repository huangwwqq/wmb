"""消费者。3 个并发，从公司任务表取未完成记录，写入公司和提单。"""
import sys
import threading
import time
sys.path.append('../')
sys.path = list(set(sys.path))
from account_queue import AccountQueue
from curd.tb_company_info import TBCompanyInfo
from curd.tb_trade_info import TBTradeInfo
from curd.tb_wmb_company_task import TBWmbCompanyTask
from setting.setting import *
from wmb_api import WmbApi, WmbBlocked, WmbLogin

_lock = threading.Lock()
_inflight = set()


class WmbConsumer:

    def __init__(self):
        self.queue = AccountQueue()
        self.task_db = TBWmbCompanyTask()
        self.company_db = TBCompanyInfo('customs_companies')
        self.trade_db = TBTradeInfo()

    def _cookie(self) -> dict:
        while True:
            _, login_data = self.queue.get_login_data()
            if not login_data:
                time.sleep(0.5)
                continue
            return login_data.get('cookie') or {}

    def _claim(self):
        with _lock:
            rows = self.task_db.unfinished(limit=30)
            for row in rows:
                company_id = str(row.get('company_id') or '')
                if company_id and company_id not in _inflight:
                    _inflight.add(company_id)
                    return row
        return None

    def _release(self, company_id: str):
        with _lock:
            _inflight.discard(str(company_id))

    def _work_one(self, api: WmbApi, task: dict):
        company_id = str(task.get('company_id'))
        db_type = int(task.get('type') or DB_BUYER)
        try:
            fetched = api.fetch_company(company_id, db_type)
        except WmbLogin:
            logger.warning(f'登录失效,公司放回 {company_id}')
            self._release(company_id)
            time.sleep(PRODUCERSLEEPTIME)
            return
        except WmbBlocked as exc:
            logger.warning(f'反爬,公司不标记完成 {company_id}: {exc}')
            self._release(company_id)
            time.sleep(BLOCK_SLEEP)
            return
        except Exception as exc:
            logger.warning(f'公司抓取异常,不标记完成 {company_id}: {exc}')
            self._release(company_id)
            time.sleep(CONSUMERSLEEPTIME)
            return
        if not fetched:
            self.task_db.mark_done(company_id)
            self._release(company_id)
            logger.info(f'公司页面没有数据,标记完成 {company_id}')
            return
        company, trades = fetched
        ok_company = self.company_db.save_info_data([company])
        ok_trade = self.trade_db.save_info_data(trades)
        if ok_company and ok_trade is not None:
            self.task_db.mark_done(company_id)
            logger.info(f'公司入库 {company_id} 提单{len(trades)}')
        else:
            logger.warning(f'入库失败,不标记完成 {company_id}')
        self._release(company_id)

    def _loop(self, index: int):
        api = WmbApi(self._cookie)
        logger.info(f'消费者线程 {index} 启动')
        while True:
            task = self._claim()
            if not task:
                time.sleep(CONSUMERSLEEPTIME)
                continue
            self._work_one(api, task)

    def run(self):
        threads = []
        for index in range(COMPANY_THREADS):
            thread = threading.Thread(target=self._loop, args=(index,), daemon=True)
            thread.start()
            threads.append(thread)
        for thread in threads:
            thread.join()


if __name__ == '__main__':
    WmbConsumer().run()
