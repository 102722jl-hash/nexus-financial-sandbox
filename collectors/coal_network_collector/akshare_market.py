"""Free prototype market adapter using AKShare.

AKShare data is treated as a third-party market proxy (T3), not exchange
source fact. Replace this adapter with a licensed provider for production.
"""
from __future__ import annotations
import argparse,hashlib,sqlite3,re
from datetime import date,datetime,timedelta,timezone
from pathlib import Path

import akshare as ak

ROOT=Path(__file__).parent; COMPANIES={'600011.SH':'华能国际','600027.SH':'华电国际','600795.SH':'国电电力'}
def now(): return datetime.now(timezone.utc).isoformat()
def number(value):
    m=re.search(r'[+-]?[0-9][0-9,]*(?:\.[0-9]+)?',str(value))
    return float(m.group(0).replace(',','')) if m else None
def latest_close(code,start=None,end=None):
    symbol=code[:6]; end=end or date.today().isoformat(); start=start or (date.today()-timedelta(days=30)).isoformat()
    frame=ak.stock_zh_a_hist(symbol=symbol,period='daily',start_date=start.replace('-',''),end_date=end.replace('-',''),adjust='')
    if frame is None or frame.empty: return None
    row=frame.iloc[-1]; day=str(row.get('日期'))[:10]; close=number(row.get('收盘'))
    return {'date':day,'close':close}
def total_shares(code):
    frame=ak.stock_individual_info_em(symbol=code[:6])
    if frame is None or frame.empty: return None
    for _,row in frame.iterrows():
        item=str(row.iloc[0]); value=row.iloc[1]
        if '总股本' in item:
            shares=number(value)
            # Eastmoney reports total shares in 10,000 shares in this endpoint.
            return shares*10000 if shares is not None else None
    return None
def insert_one(db,code,quote,shares):
    day,close=quote['date'],quote['close']; source_url='https://akshare.akfamily.xyz/data/stock/stock.html'; raw=f'{code}|{day}|{close}|AKShare'; eid='ev_'+hashlib.sha256(raw.encode()).hexdigest()[:24]
    text=f'{COMPANIES[code]} {day} 收盘价 {close} CNY/股（AKShare第三方行情）'
    db.execute("INSERT OR IGNORE INTO evidence(evidence_id,source_type,source_name,publisher,published_at,retrieved_at,original_quote,locator,source_url,data_cutoff,source_tier,temporal_role,supports_node_ids,acceptance_status,acceptance_reason) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(eid,'MARKET_PROXY','AKShare','AKShare',day+'T15:00:00+08:00',now(),text,'AKShare:stock_zh_a_hist',source_url,day,'T3','POST_EVENT_VALIDATION','[]','ACCEPTED','MARKET_PROXY_FOR_VALIDATION'))
    mid='mv_'+hashlib.sha256((raw+'|'+eid).encode()).hexdigest()[:24]
    db.execute("INSERT OR IGNORE INTO metric_values(network_id,metric_value_id,metric_code,entity_code,value,unit,currency,as_of_date,data_cutoff,value_status,evidence_id,source_table,source_column,source_row_key) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",('coal_power_v1',mid,'CLOSE_PRICE',code,close,'元/股','CNY',day,day,'MARKET_PROXY',eid,'akshare','收盘',day)); market_cap=close*shares if shares else None; status='PARTIAL_CALCULATED' if market_cap else 'DATA_MISSING'
    db.execute("INSERT OR IGNORE INTO valuation(network_id,entity_code,valuation_date,price_asof,close_price,diluted_shares,current_market_cap,data_cutoff,valuation_status,evidence_id) VALUES(?,?,?,?,?,?,?,?,?,?)",('coal_power_v1',code,day,day,close,shares,market_cap,day,status,eid)); return {'code':code,'date':day,'close':close,'shares':shares,'market_cap':market_cap,'status':status}
def run(db):
    results=[]
    for code in COMPANIES:
        try:
            quote=latest_close(code); shares=total_shares(code)
            if not quote or quote['close'] is None: results.append({'code':code,'status':'DATA_MISSING','reason':'CLOSE_NOT_FOUND'}); continue
            results.append(insert_one(db,code,quote,shares))
        except Exception as exc: results.append({'code':code,'status':'ERROR','error':str(exc)})
    db.commit(); return results
if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--db',default=str(ROOT/'coal_network.db')); a=p.parse_args(); db=sqlite3.connect(a.db); print(run(db)); db.close()
