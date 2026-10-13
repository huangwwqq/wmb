import sys
sys.path.append('../')
from common.db_supabase import PoolSupabase, DBPoolSupabase


class TBWmbTask:

    def __init__(self):
        client = PoolSupabase(schema='public')
        self.db = DBPoolSupabase(client)
        self.table_name = 'wmb_task'

    def get_one(self, country: str, db_type: int):
        rows = self.db.select(
            table=self.table_name,
            eq={'country': country, 'type': int(db_type)},
            limit=1,
        ) or []
        return rows[0] if rows else None

    def insert_new(self, country: str, db_type: int, number: int):
        return self.db.insert(table=self.table_name, items={
            'country': country,
            'type': int(db_type),
            'number': int(number),
            'flag': 0,
        })

    def mark_unfinished(self, country: str, db_type: int, number: int):
        return self.db.update(
            table=self.table_name,
            data={'number': int(number), 'flag': 0},
            eq={'country': country, 'type': int(db_type)},
        )

    def mark_done(self, country: str, db_type: int):
        return self.db.update(
            table=self.table_name,
            data={'flag': 1},
            eq={'country': country, 'type': int(db_type)},
        )

    def unfinished(self, limit: int = 20):
        return self.db.select(
            table=self.table_name,
            eq={'flag': 0},
            limit=limit,
            order_by='id',
        ) or []
