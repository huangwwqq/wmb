"""生产者。单线程。先按国家写入采购商/供应商数量，再翻页把公司 id 丢进公司任务表。"""
import sys
import time
sys.path.append('../')
sys.path = list(set(sys.path))
from account_queue import AccountQueue
from curd.tb_wmb_company_task import TBWmbCompanyTask
from curd.tb_wmb_task import TBWmbTask
from parse.country_code import build_country_index, iso2_of
from parse.parse_wmb import db_type_of
from setting.setting import *
from wmb_api import WmbApi, WmbBlocked, WmbLogin


class WmbProducer:

    def __init__(self):
        self.queue = AccountQueue()
        self.api = WmbApi(self._cookie)
        self.task_db = TBWmbTask()
        self.company_db = TBWmbCompanyTask()
        self.iso_to_en = {}

    def _cookie(self) -> dict:
        while True:
            _, login_data = self.queue.get_login_data()
            if not login_data:
                time.sleep(1)
                continue
            return login_data.get('cookie') or {}

    def _call(self, fn):
        while True:
            try:
                return fn()
            except WmbLogin:
                logger.warning('登录失效,等待重新登录')
                time.sleep(PRODUCERSLEEPTIME)
            except WmbBlocked as exc:
                logger.warning(f'反爬,不标记完成,稍后重试: {exc}')
                time.sleep(BLOCK_SLEEP)

    def refresh_counts(self):
        country_list = self._call(self.api.country_list)
        en_to_iso, self.iso_to_en = build_country_index(country_list)
        for site_type in (SITE_BUYER, SITE_SUPPLIER):
            groups = self._call(lambda st=site_type: self.api.country_stats(st))
            db_type = db_type_of(site_type)
            for group in groups:
                for item in group.get('country_list') or []:
                    en = (item.get('country_en') or '').strip().lower()
                    iso = en_to_iso.get(en) or iso2_of(en, '')
                    number = int(item.get('stats_count') or 0)
                    if not iso or number <= 0:
                        continue
                    self.iso_to_en.setdefault(iso, en)
                    old = self.task_db.get_one(iso, db_type)
                    if not old:
                        self.task_db.insert_new(iso, db_type, number)
                        logger.info(f'新国家任务 {iso} type={db_type} number={number}')
                        continue
                    old_number = int(old.get('number') or 0)
                    if number > old_number:
                        self.task_db.mark_unfinished(iso, db_type, number)
                        logger.info(f'数量增加 {iso} type={db_type} {old_number}->{number} 改未完成')

    def _fill_one(self, task: dict) -> bool:
        iso = task['country']
        db_type = int(task['type'])
        site_type = SITE_BUYER if db_type == DB_BUYER else SITE_SUPPLIER
        country_en = self.iso_to_en.get(iso)
        if not country_en:
            country_list = self._call(self.api.country_list)
            _, self.iso_to_en = build_country_index(country_list)
            country_en = self.iso_to_en.get(iso)
        if not country_en:
            logger.warning(f'{iso} 没有英文国名,跳过且不标记完成')
            return False
        start = 0
        while start < SEARCH_MAX:
            hits, rows = self._call(lambda s=start, st=site_type, name=country_en: self.api.search_companies(
                company_type=st,
                country=name,
                start=s,
            ))
            company_rows = []
            for item in rows:
                company_id = item.get('id')
                if not company_id:
                    continue
                company_rows.append({
                    'company_id': str(company_id),
                    'type': db_type,
                    'flag': 0,
                })
            self.company_db.save_ignore(company_rows)
            logger.info(f'{iso} type={db_type} start={start} 本页{len(rows)} hits={hits}')
            if not rows or len(rows) < SEARCH_PAGE_SIZE:
                return True
            start += SEARCH_PAGE_SIZE
            if start >= SEARCH_MAX or (hits and start >= min(hits, SEARCH_MAX)):
                return True
        return True

    def fill_companies(self):
        seen = set()
        while True:
            tasks = self.task_db.unfinished(limit=20)
            task = None
            for item in tasks:
                key = (item.get('country'), item.get('type'))
                if key not in seen:
                    task = item
                    break
            if not task:
                logger.info('未完成的国家任务已扫完')
                return
            key = (task.get('country'), int(task.get('type')))
            try:
                done = self._fill_one(task)
            except WmbBlocked:
                seen.add(key)
                continue
            if done:
                self.task_db.mark_done(task['country'], int(task['type']))
                logger.info(f'国家任务完成 {task["country"]} type={task["type"]}')
            else:
                seen.add(key)

    def run(self):
        logger.info('生产者开始')
        self.refresh_counts()
        self.fill_companies()
        logger.info('生产者结束')


if __name__ == '__main__':
    WmbProducer().run()
