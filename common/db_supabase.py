#!/usr/bin/env python3
# encoding: utf8

"""
Module Name: db_supabase.py
Description: PostgreSQL 操作封装（保留原类名，tb_* 不用改）
"""
import sys
sys.path.append('../')
sys.path = list(set(sys.path))
import asyncio
import json
from contextlib import contextmanager
from datetime import date, datetime
from decimal import Decimal
from typing import Union, List, Tuple, Optional, Dict, Any
from uuid import UUID

import psycopg2
from psycopg2.extras import Json, RealDictCursor, execute_values, register_default_jsonb
from psycopg2.pool import ThreadedConnectionPool
from setting.setting import *

_pool: Optional[ThreadedConnectionPool] = None


def _get_pool() -> ThreadedConnectionPool:
    global _pool
    if _pool is None or _pool.closed:
        _pool = ThreadedConnectionPool(
            minconn=1,
            maxconn=24,
            host=PGHOST,
            port=PGPORT,
            dbname=PGDATABASE,
            user=PGUSER,
            password=PGPASSWORD,
            connect_timeout=10,
        )
    return _pool


@contextmanager
def _cursor(dict_row: bool = False):
    pool = _get_pool()
    conn = pool.getconn()
    try:
        register_default_jsonb(conn)
        cur = conn.cursor(cursor_factory=RealDictCursor if dict_row else None)
        try:
            yield cur
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
    finally:
        pool.putconn(conn)


def _ident(name: str) -> str:
    return '"' + str(name).replace('"', '""') + '"'


def _adapt(v: Any):
    if isinstance(v, (dict, list)):
        return Json(v)
    return v


def _cell(v: Any):
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.isoformat()
    if isinstance(v, date):
        return v.isoformat()
    if isinstance(v, Decimal):
        if v == v.to_integral_value():
            return int(v)
        return float(v)
    if isinstance(v, UUID):
        return str(v)
    if isinstance(v, memoryview):
        return bytes(v)
    return v


def _row(r) -> dict:
    return {k: _cell(v) for k, v in dict(r).items()}


class PoolSupabase:
    """PostgreSQL 连接句柄（对应原 supabase 客户端）"""
    def __new__(cls, url: str = None, key: str = None, schema: str = 'public', **kwargs):
        obj = object.__new__(cls)
        obj.schema = schema or 'public'
        return obj


class DBPoolSupabase:
    """PostgreSQL 操作封装（对应原 DBPoolMysql / supabase）"""
    def __init__(self, client):
        self.client = client
        self.schema = getattr(client, 'schema', None) or 'public'

    def _table(self, table: str) -> str:
        return f"{_ident(self.schema)}.{_ident(table)}"

    def _cols(self, columns: str) -> str:
        raw = (columns or '*').strip()
        if raw == '*':
            return '*'
        return ', '.join(_ident(c.strip()) for c in raw.split(',') if c.strip())

    def _where(self, eq: Dict = None, neq: Dict = None,
               gte: Dict = None, gt: Dict = None,
               lte: Dict = None, lt: Dict = None):
        parts = []
        args = []

        def add(d, op):
            if not d:
                return
            for k, v in d.items():
                parts.append(f"{_ident(k)} {op} %s")
                args.append(v)

        add(eq, '=')
        add(neq, '<>')
        add(gte, '>=')
        add(gt, '>')
        add(lte, '<=')
        add(lt, '<')
        if not parts:
            return '', args
        return ' WHERE ' + ' AND '.join(parts), args

    def select(self, table: str, columns: str = '*', eq: Dict = None, neq: Dict = None,
               gte: Dict = None, gt: Dict = None, lte: Dict = None, lt: Dict = None,
               limit: int = None, order_by: str = None, desc: bool = False,
               retry_num: int = 3) -> Union[list, None]:
        """查询数据，返回字典列表"""
        where, args = self._where(eq=eq, neq=neq, gte=gte, gt=gt, lte=lte, lt=lt)
        sql = f"SELECT {self._cols(columns)} FROM {self._table(table)}{where}"
        if order_by:
            sql += f" ORDER BY {_ident(order_by)}"
            if desc:
                sql += " DESC"
        if limit is not None:
            sql += " LIMIT %s"
            args = list(args) + [int(limit)]
        for _ in range(retry_num):
            try:
                with _cursor(dict_row=True) as cur:
                    cur.execute(sql, args)
                    return [_row(r) for r in cur.fetchall()]
            except Exception as e:
                exc_type, exc_obj, exc_tb = sys.exc_info()
                logger.warning(f"{exc_type.__name__}: {e}")
        logger.error({"msg": "最大重试次数", "table": table})
        return None

    def update(self, table: str, data: Dict, eq: Dict = None, neq: Dict = None,
               gte: Dict = None, gt: Dict = None, lte: Dict = None, lt: Dict = None,
               retry_num: int = 3) -> Union[bool, None]:
        """更新数据"""
        if not data:
            return True
        sets = ', '.join(f"{_ident(k)} = %s" for k in data)
        args = [_adapt(v) for v in data.values()]
        where, wargs = self._where(eq=eq, neq=neq, gte=gte, gt=gt, lte=lte, lt=lt)
        sql = f"UPDATE {self._table(table)} SET {sets}{where}"
        args = args + list(wargs)
        for _ in range(retry_num):
            try:
                with _cursor() as cur:
                    cur.execute(sql, args)
                return True
            except Exception as e:
                exc_type, exc_obj, exc_tb = sys.exc_info()
                logger.warning(f"{exc_type.__name__}: {e}")
        logger.error({"msg": "最大重试次数", "table": table, "data": data})
        return None

    def insert(self, table: str, items: Union[List[dict], dict],
               retry_num: int = 3) -> Union[bool, None]:
        """插入数据"""
        rows = items if isinstance(items, list) else [items]
        if not rows:
            return True
        keys = []
        seen = set()
        for item in rows:
            for k in item:
                if k not in seen:
                    seen.add(k)
                    keys.append(k)
        cols_sql = ', '.join(_ident(k) for k in keys)
        values = [tuple(_adapt(item.get(k)) for k in keys) for item in rows]
        sql = f"INSERT INTO {self._table(table)} ({cols_sql}) VALUES %s"
        for _ in range(retry_num):
            try:
                with _cursor() as cur:
                    execute_values(cur, sql, values, page_size=100)
                return True
            except Exception as e:
                exc_type, exc_obj, exc_tb = sys.exc_info()
                logger.warning(f"{exc_type.__name__}: {e}")
        logger.error({"msg": "最大重试次数", "table": table})
        return None

    def count(self, table: str, eq: Dict = None, neq: Dict = None,
              gte: Dict = None, gt: Dict = None, lte: Dict = None, lt: Dict = None,
              retry_num: int = 3) -> Optional[int]:
        """统计数量"""
        where, args = self._where(eq=eq, neq=neq, gte=gte, gt=gt, lte=lte, lt=lt)
        sql = f"SELECT COUNT(*) AS n FROM {self._table(table)}{where}"
        for _ in range(retry_num):
            try:
                with _cursor(dict_row=True) as cur:
                    cur.execute(sql, args)
                    row = cur.fetchone()
                    return int(row['n']) if row else 0
            except Exception as e:
                exc_type, exc_obj, exc_tb = sys.exc_info()
                logger.warning(f"{exc_type.__name__}: {e}")
        logger.error({"msg": "最大重试次数", "table": table})
        return None

    def save(self, table: str, items: Union[List[dict], Tuple[dict]],
             unique_field_list: list = None, ignore: bool = False):
        """
        批量写入（upsert）
        :param table: 表名
        :param items: 数据列表
        :param unique_field_list: 冲突时用于判断的唯一字段
        :param ignore: True 时冲突忽略（不更新）
        """
        logger.info({"len": len(items), "pre": json.dumps(items, ensure_ascii=False)[:100]})
        if len(items) == 0:
            return
        if unique_field_list:
            deduped = []
            seen = set()
            for item in items:
                key = tuple(item.get(f) for f in unique_field_list)
                if key in seen:
                    continue
                seen.add(key)
                deduped.append(item)
            items = deduped
            if not items:
                return
        keys = []
        seen_k = set()
        for item in items:
            for k in item:
                if k not in seen_k:
                    seen_k.add(k)
                    keys.append(k)
        cols_sql = ', '.join(_ident(k) for k in keys)
        values = [tuple(_adapt(item.get(k)) for k in keys) for item in items]
        sql = f"INSERT INTO {self._table(table)} ({cols_sql}) VALUES %s"
        if unique_field_list:
            conflict = ', '.join(_ident(f) for f in unique_field_list)
            if ignore:
                sql += f" ON CONFLICT ({conflict}) DO NOTHING"
            else:
                uniq = set(unique_field_list)
                updates = [
                    f"{_ident(k)} = EXCLUDED.{_ident(k)}"
                    for k in keys if k not in uniq and k != 'id'
                ]
                if updates:
                    sql += f" ON CONFLICT ({conflict}) DO UPDATE SET " + ', '.join(updates)
                else:
                    sql += f" ON CONFLICT ({conflict}) DO NOTHING"
        for _ in range(3):
            try:
                with _cursor() as cur:
                    execute_values(cur, sql, values, page_size=100)
                return True
            except Exception as e:
                exc_type, exc_obj, exc_tb = sys.exc_info()
                logger.warning(f"{exc_type.__name__}: {e}")
        logger.error({"msg": "最大重试次数", "table": table})

    @staticmethod
    def id_iterator(min_id: int, max_id: int, batch_size: int) -> tuple:
        for i in range(min_id, max_id + 1, batch_size):
            yield i, min(i + batch_size - 1, max_id)

    def read_id_range(self, table: str, id_name: str = 'id',
                      eq: Dict = None) -> tuple:
        """获取表中 id 的最小最大值"""
        where, args = self._where(eq=eq)
        col = _ident(id_name)
        tbl = self._table(table)
        try:
            with _cursor(dict_row=True) as cur:
                cur.execute(
                    f"SELECT {col} FROM {tbl}{where} ORDER BY {col} ASC LIMIT 1",
                    args,
                )
                min_row = cur.fetchone()
                cur.execute(
                    f"SELECT {col} FROM {tbl}{where} ORDER BY {col} DESC LIMIT 1",
                    args,
                )
                max_row = cur.fetchone()
            if not min_row or not max_row:
                return (0, 0)
            return (min_row[id_name], max_row[id_name])
        except Exception as e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            logger.warning(f"{exc_type.__name__}: {e}")
            return (0, 0)

    def test_connect(self):
        try:
            with _cursor(dict_row=True) as cur:
                cur.execute('SELECT id FROM public.wmb_task LIMIT 1')
                data = [_row(r) for r in cur.fetchall()]
            logger.info({"msg": "postgresql连接成功", "data": data})
        except Exception as e:
            logger.error({"msg": "postgresql连接失败", "error": str(e)})

    def close(self):
        pass


class AsyncDBPoolSupabase:
    """异步 PostgreSQL 操作封装"""
    def __init__(self, client):
        self.client = client
        self.__db = DBPoolSupabase(self.client)

    async def select(self, *args, **kwargs):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: self.__db.select(*args, **kwargs))

    async def update(self, *args, **kwargs):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: self.__db.update(*args, **kwargs))

    async def insert(self, *args, **kwargs):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: self.__db.insert(*args, **kwargs))

    async def count(self, *args, **kwargs):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: self.__db.count(*args, **kwargs))

    async def save(self, table: str, items: Union[List[dict], Tuple[dict]],
                   unique_field_list: list = None, ignore: bool = False):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, lambda: self.__db.save(table, items, unique_field_list, ignore)
        )

    async def read_id_range(self, table: str, id_name: str = 'id', eq: Dict = None) -> tuple:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: self.__db.read_id_range(table, id_name, eq))

    @staticmethod
    async def id_iterator_async(min_id: int, max_id: int, batch_size: int):
        for i in range(min_id, max_id + 1, batch_size):
            yield i, min(i + batch_size - 1, max_id)

    async def test_connect(self):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.__db.test_connect)

    async def close(self):
        pass
