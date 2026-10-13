import sys
from datetime import datetime, timezone
sys.path.append('../')
from common.db_supabase import PoolSupabase, DBPoolSupabase
from setting.setting import SOURCE


class TBTradeInfo:

    def __init__(self):
        client = PoolSupabase(schema='customs')
        self.db = DBPoolSupabase(client)
        self.table_name = 'trade_info'

    def save_info_data(self, info_list):
        now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S.%f%z')
        if now.endswith('+0000'):
            now = now[:-5] + '+00'
        rows = []
        for item in info_list or []:
            row = dict(item)
            if not row.get('trade_id'):
                continue
            row.pop('id', None)
            row['source'] = row.get('source') or SOURCE
            row['update_time'] = now
            if not row.get('create_time'):
                row['create_time'] = now
            rows.append(row)
        if not rows:
            return True
        return self.db.save(
            table=self.table_name,
            items=rows,
            unique_field_list=['trade_id'],
        )
