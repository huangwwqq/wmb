import sys
sys.path.append('../')
from common.db_supabase import PoolSupabase, DBPoolSupabase
from setting.setting import SOURCE


class TBCompanyInfo:

    def __init__(self, table_name: str = 'customs_companies'):
        client = PoolSupabase(schema='public')
        self.db = DBPoolSupabase(client)
        self.table_name = table_name

    def save_info_data(self, info_list):
        rows = []
        for item in info_list or []:
            row = dict(item)
            row.pop('id', None)
            if not row.get('company_id'):
                continue
            row['source'] = row.get('source') or SOURCE
            rows.append(row)
        if not rows:
            return True
        return self.db.save(
            table=self.table_name,
            items=rows,
            unique_field_list=['source', 'company_id'],
        )
