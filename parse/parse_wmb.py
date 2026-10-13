"""把外贸邦公司详情 / 提单映射进海关表。没有的字段不写，不补造。"""
import json
import re

from parse.country_code import iso2_of

SOURCE = 'wmb'


def _s(value) -> str:
    if value is None:
        return ''
    return str(value).strip()


def _date(value) -> str:
    text = _s(value)
    if 'T' in text:
        text = text.split('T', 1)[0]
    return text.replace('/', '-')


def site_type_of(db_type: int) -> int:
    return 0 if int(db_type) == 1 else 1


def db_type_of(site_type: int) -> int:
    return 1 if int(site_type) == 0 else 2


def role_of(site_type: int) -> int:
    """本公司角色：1 进口商，2 出口商。"""
    return 1 if int(site_type) == 0 else 2


def parse_company_details(html: str) -> dict:
    mark = 'company_details='
    idx = html.find(mark)
    if idx < 0:
        return {}
    start = html.find('{', idx)
    if start < 0:
        return {}
    try:
        data, _ = json.JSONDecoder().raw_decode(html[start:])
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _contacts(detail: dict, contact: dict) -> list:
    contact = contact or {}
    emails = [x.strip() for x in re.split(r'[;,]', _s(contact.get('email'))) if x.strip()]
    phone = _s(contact.get('tel'))
    fax = _s(contact.get('fax'))
    web = _s(contact.get('web'))
    name = _s(detail.get('contact'))
    address = _s(detail.get('address'))
    if not any([emails, phone, fax, web, name]):
        return []
    if not emails:
        emails = ['']
    rows = []
    for email in emails:
        item = {}
        if name:
            item['name'] = name
        if email:
            item['email'] = email
        if phone:
            item['phone'] = phone
        if fax:
            item['fax'] = fax
        if web:
            item['website'] = web
        if address:
            item['address'] = address
        if item:
            rows.append(item)
    return rows


def _products(items: list) -> list:
    out = []
    seen = set()
    for item in items or []:
        if isinstance(item, str):
            name = item.strip()
        elif isinstance(item, dict):
            name = _s(item.get('value') or item.get('product'))
        else:
            continue
        key = name.lower()
        if not name or key in seen:
            continue
        seen.add(key)
        out.append(name)
    return out


def build_company_row(
    detail: dict,
    contact: dict,
    trends: dict,
    year_stats: list,
    partners: list,
    hs_list: list,
    products: list,
    areas: list,
    ports: list,
    trade_preview: list,
    site_type: int,
    trade_hits: int,
) -> dict:
    country_en = _s(detail.get('country_en') or detail.get('country'))
    country_cn = _s(detail.get('country_cn'))
    code = iso2_of(country_en)
    role = role_of(site_type)
    partner_rows = []
    for item in partners or []:
        partner_rows.append({
            'company_name': _s(item.get('name')),
            'country_iso': iso2_of(_s(item.get('country'))) or _s(item.get('country')),
            'count': item.get('bill_count') or 0,
            'last_day': _date(item.get('last_trade_date')),
            'company_type': role,
        })
    hs_rows = []
    for item in hs_list or []:
        hs_rows.append({
            'hscode': _s(item.get('hs') or item.get('value_hs')),
            'desc': _s(item.get('desc')),
            'count': item.get('bill_count') or item.get('count_hs') or 0,
            'last_date': _date(item.get('last_trade_date') or item.get('last_trade_date_hs')),
            'company_type': role,
        })
    word_key = 'import' if role == 1 else 'export'
    words = {}
    for item in products or []:
        name = _s(item.get('value') or item.get('product'))
        if name:
            words[name] = item.get('count') or item.get('bill_count') or 0
    preview = []
    for item in (trade_preview or [])[:20]:
        preview.append({
            'date': _date(item.get('date')),
            'seller': _s(item.get('seller')),
            'seller_country_code': iso2_of(_s(item.get('seller_country_ori') or item.get('seller_country'))),
            'buyer': _s(item.get('buyer')),
            'buyer_country_code': iso2_of(_s(item.get('buyer_country_ori') or item.get('buyer_country'))),
            'hscode': _s(item.get('hs')),
            'desc': _s(item.get('descript')),
            'price': _s(item.get('amount') if item.get('amount') is not None else item.get('uusd')),
            'price_unit': 'USD' if item.get('uusd') is not None and item.get('amount') is None else '',
        })
    top = partner_rows[0] if partner_rows else {}
    bill_count = int(detail.get('bill_count') or trade_hits or 0)
    last_buyer = _date(detail.get('last_trade_date_buyer'))
    last_seller = _date(detail.get('last_trade_date_seller'))
    last_trade = _date(detail.get('last_trade_date'))
    row = {
        'source': SOURCE,
        'company_id': _s(detail.get('id')),
        'company_name': _s(detail.get('name')),
        'company_country': country_cn or country_en,
        'company_country_code': code,
        'main_products': _products(detail.get('product')) or _products(products),
        'location': _s(detail.get('address')),
        'concat_list': _contacts(detail, contact),
        'trade_sort': [
            {'name': _s(x.get('value') or x.get('product')), 'count': x.get('count') or 0, 'prop': x.get('prop'), 'last_date': _date(x.get('last_trade_date'))}
            for x in (products or []) if _s(x.get('value') or x.get('product'))
        ],
        'trade_trend': trends or [],
        'trader_statistics': partner_rows,
        'hscode_statistics': [x for x in hs_rows if x.get('hscode')],
        'custom_records': preview,
        'wordcloud': {'export': words if word_key == 'export' else {}, 'import': words if word_key == 'import' else {}},
        'raw_data': {
            'company_details': detail,
            'contact': contact or {},
            'year_stats': year_stats or [],
            'areas': areas or [],
            'ports': ports or [],
            'site_type': site_type,
        },
    }
    web = _s((contact or {}).get('web'))
    phone = _s((contact or {}).get('tel'))
    if web:
        row['site_url'] = web
    if phone:
        row['phone'] = phone
    if role == 1:
        row['import_count'] = bill_count
        row['last_import_time'] = last_buyer or last_trade
        if top:
            row['max_seller_name'] = top.get('company_name') or ''
            row['max_seller_country'] = top.get('country_iso') or ''
    else:
        row['export_count'] = bill_count
        row['last_export_time'] = last_seller or last_trade
        if top:
            row['max_buyer_name'] = top.get('company_name') or ''
            row['max_buyer_country'] = top.get('country_iso') or ''
    return row


def build_trade_rows(bills: list, site_type: int) -> list:
    rows = []
    record_type = '进口' if int(site_type) == 0 else '出口'
    for item in bills or []:
        bill_id = item.get('id')
        if bill_id is None:
            bill_id = item.get('bill_id')
        if bill_id is None:
            continue
        buyer_country = _s(item.get('buyer_country_ori') or item.get('buyer_country'))
        seller_country = _s(item.get('seller_country_ori') or item.get('seller_country'))
        source_name = _s(item.get('source')).split('_', 1)[0]
        row = {
            'trade_id': f'wmb:{bill_id}',
            'record_type': record_type,
            'country_name': source_name,
            'shpmt_date': _date(item.get('date')),
            'hs_code': _s(item.get('hs')),
            'buyer_name': _s(item.get('buyer')),
            'buyer_country': buyer_country,
            'buyer_country_code': iso2_of(buyer_country),
            'buyer_id': _s(item.get('buyer_id_std') or item.get('buyer_id')),
            'seller_name': _s(item.get('seller')),
            'seller_country': seller_country,
            'seller_country_code': iso2_of(seller_country),
            'seller_id': _s(item.get('seller_id_std') or item.get('seller_id')),
            'departure_port': _s(item.get('seller_port')),
            'destination_port': _s(item.get('buyer_port')),
            'product_desc': _s(item.get('descript')),
            'quantity': _s(item.get('qty')),
            'quantity_util': _s(item.get('qty_unit')),
            'weight_kg': _s(item.get('weight')),
            'containers_number': _s(item.get('container')),
            'transport_method': _s(item.get('trans')),
            'bill_of_lading_num': _s(item.get('bill_no')),
            'source': SOURCE,
        }
        if item.get('amount') is not None:
            row['price_usd'] = _s(item.get('amount'))
        if item.get('uusd') is not None:
            row['unit_price'] = _s(item.get('uusd'))
        rows.append(row)
    return rows
