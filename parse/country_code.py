"""站点国家英文名 -> ISO 二字码。countrycode2 已经是两位字母时直接用。"""

# 站点给的不是两位码，或码是错的
FIX = {
    'india': 'IN',
    'south korea': 'KR',
    'trinidad and tobago': 'TT',
    'serbia': 'RS',
    'vanuatu': 'VU',
    'virgin islands (u.s.)': 'VI',
    'northern mariana islands': 'MP',
    'kosovo': 'XK',
    'south georgia and the south sandwich islands': 'GS',
    'serbia and montenegro': 'ME',
    'republic of montenegro': 'ME',
    'saint vincent and the grenadines': 'VC',
    'guernsey': 'GG',
    'south ossetia': 'OS',
    'saint-martin': 'MF',
    'sint maarten': 'SX',
    'guinea-bissau': 'GW',
    'palestine': 'PS',
    'mauritania': 'MR',
    'the democratic republic of the congo': 'CD',
    'croatia': 'HR',
    'the dominican rep.': 'DO',
    'saotomeandprincipe': 'ST',
    'monsrat': 'MS',
    'montserrat': 'MS',
    'fedrated states of micron': 'FM',
    'western samoa': 'WS',
    'united states outlying islands': 'UM',
    'england': 'GB',
    'burma': 'MM',
    'czech republic': 'CZ',
    'russia': 'RU',
    'vietnam': 'VN',
    'taiwan': 'TW',
    'hong kong': 'HK',
    'macao': 'MO',
    'united states': 'US',
    'china': 'CN',
    'japan': 'JP',
    'germany': 'DE',
    'france': 'FR',
    'italy': 'IT',
    'spain': 'ES',
    'canada': 'CA',
    'mexico': 'MX',
    'brazil': 'BR',
    'australia': 'AU',
    'indonesia': 'ID',
    'thailand': 'TH',
    'malaysia': 'MY',
    'singapore': 'SG',
    'philippines': 'PH',
    'netherlands': 'NL',
    'belgium': 'BE',
    'poland': 'PL',
    'sweden': 'SE',
    'switzerland': 'CH',
    'austria': 'AT',
    'portugal': 'PT',
    'greece': 'GR',
    'ireland': 'IE',
    'new zealand': 'NZ',
    'south africa': 'ZA',
    'egypt': 'EG',
    'saudi arabia': 'SA',
    'united arab emirates': 'AE',
    'argentina': 'AR',
    'chile': 'CL',
    'colombia': 'CO',
    'peru': 'PE',
    'ecuador': 'EC',
    'pakistan': 'PK',
    'bangladesh': 'BD',
    'sri lanka': 'LK',
    'south korea': 'KR',
    'd.p.r.korea': 'KP',
    'east timor': 'TL',
    'cape verde': 'CV',
    'ivory coast': 'CI',
    "cote d'ivoire": 'CI',
    'laos': 'LA',
    'syria': 'SY',
    'turkey': 'TR',
    'tanzania': 'TZ',
    'venezuela': 'VE',
    'bolivia': 'BO',
    'brunei': 'BN',
    'moldova': 'MD',
    'macedonia': 'MK',
    'swaziland': 'SZ',
    'eswatini': 'SZ',
}

# 不是国家，不进任务表
SKIP = {
    'customs union',
    'unknown country',
    'mid',
    'atlantic',
    'leeward islands',
    'southern asia',
    'pacific islands',
    'other',
    'czechoslovakia',
    'azores',
    'ussr(formerly)',
    'yugoslavia',
}


def iso2_of(country_en: str, countrycode2: str = '') -> str:
    name = (country_en or '').strip().lower()
    if not name or name in SKIP:
        return ''
    if name in FIX:
        return FIX[name]
    code = (countrycode2 or '').strip().upper()
    if len(code) == 2 and code.isalpha():
        return code
    return ''


def build_country_index(country_list: list) -> tuple:
    """返回 (英文小写 -> 二字码, 二字码 -> 英文小写)。"""
    en_to_iso = {}
    iso_to_en = {}
    for item in country_list or []:
        en = (item.get('country_en') or '').strip()
        iso = iso2_of(en, item.get('countrycode2') or '')
        if not iso:
            continue
        key = en.lower()
        en_to_iso[key] = iso
        iso_to_en.setdefault(iso, key)
    return en_to_iso, iso_to_en
