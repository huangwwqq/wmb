"""外贸邦接口。国家数量走 /async/common/country/stats，公司列表走 /async/company/search/list。"""
import json
import re
import sys
import time
from datetime import datetime, timedelta
sys.path.append('../')
from common.requests_tool import request_get, request_post
from parse.parse_wmb import (
    build_company_row,
    build_trade_rows,
    parse_company_details,
    site_type_of,
)
from setting.setting import *

BLOCK_WORDS = ('验证码', '频繁', '机器人', '限制访问', '访问过于')
BLOCK_STATES = {10, 1000, 2000, 403, 429, '10', '1000', '2000', '403', '429'}


class WmbBlocked(Exception):
    pass


class WmbLogin(Exception):
    pass


class WmbApi:

    def __init__(self, cookie_getter, gap: float = 0):
        self.cookie_getter = cookie_getter
        self.gap = gap
        self._last = 0.0

    def _cookie(self) -> dict:
        if self.gap:
            wait = self.gap - (time.time() - self._last)
            if wait > 0:
                time.sleep(wait)
        cookies = self.cookie_getter()
        self._last = time.time()
        if isinstance(cookies, str):
            cookies = json.loads(cookies)
        if not cookies:
            raise WmbLogin('没有可用 cookie')
        return cookies

    @staticmethod
    def _blocked(status: int, payload, text: str) -> bool:
        if status in (403, 412, 429, 503):
            return True
        message = ''
        state = None
        if isinstance(payload, dict):
            state = payload.get('state')
            message = str(payload.get('message') or '')
        blob = f'{message}\n{text or ""}'
        if state in BLOCK_STATES:
            return True
        return any(word in blob for word in BLOCK_WORDS)

    def _read(self, response):
        if response is None:
            raise WmbBlocked('请求无响应')
        text = response.text or ''
        status = getattr(response, 'status_code', 0) or 0
        payload = None
        try:
            payload = response.json()
        except Exception:
            payload = None
        if self._blocked(status, payload, text):
            raise WmbBlocked(f'反爬或限流 status={status} body={text[:180]}')
        if '会员登录' in text and 'company_details' not in text:
            raise WmbLogin('登录失效')
        return status, text, payload

    def get(self, path: str, params: dict = None):
        response = request_get(
            BASE_URL + path,
            headers=HEADER,
            params=params,
            cookies=self._cookie(),
        )
        status, text, payload = self._read(response)
        if not isinstance(payload, dict):
            raise WmbBlocked(f'接口不是 JSON status={status} body={text[:180]}')
        return payload

    def post(self, path: str, data: dict):
        headers = dict(HEADER)
        headers['Content-Type'] = 'application/x-www-form-urlencoded; charset=UTF-8'
        response = request_post(
            BASE_URL + path,
            headers=headers,
            data=data,
            cookies=self._cookie(),
        )
        status, text, payload = self._read(response)
        if not isinstance(payload, dict):
            raise WmbBlocked(f'接口不是 JSON status={status} body={text[:180]}')
        return payload

    def get_html(self, path: str) -> str:
        response = request_get(
            BASE_URL + path,
            headers=HEADER,
            cookies=self._cookie(),
        )
        status, text, _ = self._read(response)
        if status == 404:
            return ''
        if status >= 400:
            raise WmbBlocked(f'页面状态 {status}')
        return text

    @staticmethod
    def search_params(
        company_type: int,
        country: str = '*',
        key: str = '*',
        hs: str = '*',
        search_type: int = 2,
        start: int = 0,
        size: int = SEARCH_PAGE_SIZE,
        filter_weight: str = FILTER_WEIGHT,
    ) -> dict:
        # search_type: 1 公司名，2 产品名，3 HS 编码
        return {
            'start': start,
            'key': key or '*',
            'hs': hs or '*',
            'company_type': company_type,
            'off_line_counties': '*',
            'search_type': search_type,
            'search_language': 0,
            'search_relation': 0,
            'sort': 'default',
            'country': (country or '*').lower(),
            'filter_bill_count_min': 0,
            'filter_bill_count_max': 0,
            'filter_weight': filter_weight,
            'trade_countries': '*',
            'buyer_ports': '*',
            'seller_ports': '*',
            'is_precise': 0,
            'is_new': 0,
            'is_trans': 0,
            'is_bs': 0,
            'is_gs': 0,
            'is_logistics': 0,
            'filter_date_start': '*',
            'filter_date_end': '*',
            'only_phrase': 0,
            'size': size,
        }

    def country_list(self) -> list:
        payload = self.get('/async/common/countries', {'tier': 0})
        return payload.get('country_list') or []

    def country_stats(self, company_type: int, filter_weight: str = FILTER_WEIGHT) -> list:
        params = self.search_params(company_type=company_type, filter_weight=filter_weight, size=1)
        params.pop('sort', None)
        params.pop('country', None)
        params.pop('size', None)
        payload = self.get('/async/common/country/stats', params)
        if payload.get('state') not in (0, '0', None):
            raise WmbBlocked(f'国家数量 state={payload.get("state")} {payload.get("message")}')
        return ((payload.get('data') or {}).get('list')) or []

    def search_companies(self, company_type: int, country: str, start: int, key: str = '*', hs: str = '*',
                         search_type: int = 2, filter_weight: str = FILTER_WEIGHT, size: int = SEARCH_PAGE_SIZE):
        params = self.search_params(
            company_type=company_type,
            country=country,
            key=key,
            hs=hs,
            search_type=search_type,
            start=start,
            size=size,
            filter_weight=filter_weight,
        )
        # /async/company/search/list 每次只回 1 条。页面实际翻页走 /async/company/search，一页 30 个公司。
        payload = self.get('/async/company/search', params)
        content = payload.get('content') or ''
        seen = []
        for company_id in re.findall(r'/(?:buyer|supplier)/(\d+)', content):
            if company_id not in seen:
                seen.append(company_id)
        rows = [{'id': company_id} for company_id in seen]
        return int(payload.get('total') or 0), rows

    def _node_list(self, payload: dict, key: str):
        node = payload.get(key) or {}
        if not isinstance(node, dict):
            return [], 0
        state = node.get('state')
        if state not in (0, '0', None) and state not in BLOCK_STATES:
            # 没数据时有的接口直接给非 0，不当成反爬
            if state in (10000, '10000'):
                return [], 0
        if state in BLOCK_STATES:
            raise WmbBlocked(f'{key} state={state}')
        data = node.get('data') or {}
        rows = data.get('list') or []
        hits = data.get('hits')
        if hits is None:
            hits = data.get('total_count') or len(rows)
        return rows, int(hits or 0)

    def _detail_base(self, company_id, site_type: int, last_date: str, token: str) -> dict:
        end_time = (last_date or '')[:10] or datetime.now().strftime('%Y-%m-%d')
        try:
            start_day = (datetime.strptime(end_time, '%Y-%m-%d') - timedelta(days=365 * 10)).strftime('%Y-%m-%d')
        except Exception:
            start_day = '2016-01-01'
        return {
            'id': company_id,
            'company_type': site_type,
            'end_time': end_time,
            'last_trade_date': end_time,
            'country': '*',
            'key': '*',
            'product': '*',
            'sort': 'default',
            'start_time': start_day,
            'seo_flag': 0,
            'is_page': 'true',
            'start': 0,
            'size': DETAIL_PAGE_SIZE,
            'tag_id': 0,
            'perms_token': token,
            'port_type': site_type,
            'scene': 1,
        }

    def _trade_pages(self, base: dict) -> tuple:
        bills = []
        hits = 0
        start = 0
        while start < SEARCH_MAX:
            params = dict(base)
            params.update({
                'start': start,
                'size': TRADE_PAGE_SIZE,
                'scene': 4,
                'is_page': 'true',
            })
            payload = self.get('/company/detail/trade', params)
            trade = payload.get('trade') or {}
            state = trade.get('state')
            if state in BLOCK_STATES:
                raise WmbBlocked(f'提单 state={state}')
            data = trade.get('data') or {}
            chunk = data.get('list') or []
            hits = int(data.get('hits') or hits or 0)
            bills.extend(chunk)
            if len(chunk) < TRADE_PAGE_SIZE:
                break
            start += TRADE_PAGE_SIZE
        return bills, hits

    def fetch_company(self, company_id, db_type: int):
        site_type = site_type_of(db_type)
        detail = {}
        for try_type in (site_type, 1 - site_type):
            route = 'buyer' if try_type == 0 else 'supplier'
            html = self.get_html(f'/{route}/{company_id}')
            detail = parse_company_details(html)
            if detail.get('id'):
                site_type = int(detail.get('type') if detail.get('type') in (0, 1, '0', '1') else try_type)
                break
        if not detail.get('id'):
            return None
        perms = self.get('/async/company/detail/perms', {'company_id': company_id})
        token = perms.get('perms_token') or ''
        contact_payload = self.post('/async/company/contacts', {
            'ctoken': detail.get('ctoken') or '',
            'perms_token': token,
            'id': company_id,
        })
        contact = contact_payload.get('data') if isinstance(contact_payload.get('data'), dict) else {}
        last_date = detail.get('last_trade_date') or detail.get('last_trade_date_buyer') or detail.get('last_trade_date_seller') or ''
        base = self._detail_base(company_id, int(site_type), str(last_date), token)
        trends_payload = self.get('/company/detail/trends', dict(base, calendar_interval='month', size=5))
        trends = (trends_payload.get('data') or {}) if trends_payload.get('state') in (0, '0', None) else {}
        year_payload = self.get('/company/detail/year/stats', base)
        year_stats = ((year_payload.get('data') or {}).get('list') or []) if isinstance(year_payload.get('data'), dict) else []
        partners, _ = self._node_list(self.get('/company/detail/partner', dict(base, sort='bill_counts')), 'partner')
        hs_list, _ = self._node_list(self.get('/company/detail/hs', base), 'hs')
        products, _ = self._node_list(self.get('/async/detail/product-list', base), 'product')
        areas, _ = self._node_list(self.get('/company/detail/trade-country', base), 'country')
        ports_in, _ = self._node_list(self.get('/company/detail/port', dict(base, port_type=0)), 'port')
        ports_out, _ = self._node_list(self.get('/company/detail/port', dict(base, port_type=1)), 'port')
        ports = [{'port_type': 0, **item} for item in ports_in] + [{'port_type': 1, **item} for item in ports_out]
        bills, hits = self._trade_pages(base)
        other_bills = []
        if detail.get('last_trade_date_buyer') and detail.get('last_trade_date_seller'):
            other_type = 1 - int(site_type)
            other_base = self._detail_base(company_id, other_type, str(last_date), token)
            other_partners, _ = self._node_list(
                self.get('/company/detail/partner', dict(other_base, sort='bill_counts')),
                'partner',
            )
            other_hs, _ = self._node_list(self.get('/company/detail/hs', other_base), 'hs')
            other_products, _ = self._node_list(self.get('/async/detail/product-list', other_base), 'product')
            other_bills, other_hits = self._trade_pages(other_base)
            partners = list(partners) + list(other_partners)
            hs_list = list(hs_list) + list(other_hs)
            products = list(products) + list(other_products)
        partners = sorted(partners, key=lambda x: x.get('bill_count') or 0, reverse=True)
        company = build_company_row(
            detail=detail,
            contact=contact,
            trends=trends,
            year_stats=year_stats,
            partners=partners,
            hs_list=hs_list or detail.get('hs') or [],
            products=products or detail.get('product') or [],
            areas=areas,
            ports=ports,
            trade_preview=bills,
            site_type=int(site_type),
            trade_hits=hits,
        )
        company['raw_data']['year_stats'] = year_stats
        trades = build_trade_rows(bills, int(site_type))
        if other_bills:
            other_type = 1 - int(site_type)
            trades.extend(build_trade_rows(other_bills, other_type))
            if other_type == 0:
                company['import_count'] = int(other_hits or 0)
            else:
                company['export_count'] = int(other_hits or 0)
        return company, trades
