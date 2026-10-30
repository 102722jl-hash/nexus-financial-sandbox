"""Public Sina daily K-line adapter for the three thermal-power companies."""
from __future__ import annotations
import argparse,hashlib,json,re,sqlite3,urllib.request
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).parent; COMPANIES={'600011.SH':'华能国际','600027.SH':'华电国际','600795.SH':'国电电力'}
BASE='https://quotes.sina.cn/cn/api/jsonp_v2.php/var%20_data=/CN_MarketData.getKLineData'
def now(): return datetime.now(timezone.utc).isoformat()
def fetch(code,datalen=400):
    symbol='sh'+code[:6]; url=f'{BASE}?symbol={symbol}&scale=240&ma=no&datalen={datalen}'
    req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0','Referer':'https://finance.sina.com.cn/'})
    with urllib.request.urlopen(req,timeout=45) as r: raw=r.read().decode('utf-8','ignore')
    m=re.search(r'var\s+_data=\((\[.*\])\);?',raw,re.S)
    if not m: raise ValueError('Sina K-line response format not recognized')
    return url,json.loads(m.group(1))
def insert(db,code,url,items):
    inserted=0
    for item in items:
        day=item.get('day'); close=float(item['close']); quote=f'{COMPANIES[code]} {day} 收盘价 {close} CNY/股（新浪公开日线）'; eid='ev_'+hashlib.sha256((url+'|'+quote).encode()).hexdigest()[:24]
        db.execute("INSERT OR IGNORE INTO evidence(evidence_id,source_type,source_name,publisher,published_at,retrieved_at,original_quote,locator,source_url,data_cutoff,source_tier,temporal_role,supports_node_ids,acceptance_status,acceptance_reason) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(eid,'MARKET_PROXY','Sina daily K-line','新浪财经',day+'T15:00:00+08:00',now(),quote,f'json:day:{day}',url,day,'T3','POST_EVENT_VALIDATION','[]','ACCEPTED','MARKET_PROXY_FOR_VALIDATION'))
        mid='mv_'+hashlib.sha256((code+'|'+day+'|'+str(close)+'|'+eid).encode()).hexdigest()[:24]
        db.execute("INSERT OR IGNORE INTO metric_values(network_id,metric_value_id,metric_code,entity_code,value,unit,currency,as_of_date,data_cutoff,value_status,evidence_id,source_table,source_column,source_row_key) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",('coal_power_v1',mid,'CLOSE_PRICE',code,close,'元/股','CNY',day,day,'MARKET_PROXY',eid,'sina_kline','close',day)); inserted+=db.execute('SELECT changes()').fetchone()[0]
    return inserted
def run(db):
    result=[]
    for code in COMPANIES:
        try:
            url,items=fetch(code); count=insert(db,code,url,items); latest=items[-1] if items else {}; result.append({'code':code,'rows':count,'latest':latest,'status':'OK'})
        except Exception as exc: result.append({'code':code,'status':'ERROR','error':str(exc)})
    db.commit(); return result
if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--db',default=str(ROOT/'coal_network.db')); a=p.parse_args(); db=sqlite3.connect(a.db); print(json.dumps(run(db),ensure_ascii=False,indent=2)); db.close()
