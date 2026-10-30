"""Corrected Sina market importer."""
import hashlib,json,sqlite3
from pathlib import Path
from sina_market import ROOT,COMPANIES,fetch,now
def insert(db,code,url,items):
    inserted=0
    for item in items:
        day=item['day']; close=float(item['close']); quote=f'{COMPANIES[code]} {day} 收盘价 {close} CNY/股（新浪公开日线）'; eid='ev_'+hashlib.sha256((url+'|'+quote).encode()).hexdigest()[:24]
        db.execute("INSERT OR IGNORE INTO evidence(evidence_id,source_type,source_name,publisher,published_at,retrieved_at,original_quote,locator,source_url,data_cutoff,source_tier,temporal_role,supports_node_ids,acceptance_status,acceptance_reason) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(eid,'MARKET_PROXY','Sina daily K-line','新浪财经',day+'T15:00:00+08:00',now(),quote,f'json:day:{day}',url,day,'T3','POST_EVENT_VALIDATION','[]','ACCEPTED','MARKET_PROXY_FOR_VALIDATION'))
        mid='mv_'+hashlib.sha256((code+'|'+day+'|'+str(close)+'|'+eid).encode()).hexdigest()[:24]
        db.execute("INSERT OR IGNORE INTO metric_values(network_id,metric_value_id,metric_code,entity_code,value,unit,currency,as_of_date,data_cutoff,value_status,evidence_id,source_table,source_column,source_row_key) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",('coal_power_v1',mid,'CLOSE_PRICE',code,close,'元/股','CNY',day,day,'MARKET_PROXY',eid,'sina_kline','close',day)); inserted+=db.execute('SELECT changes()').fetchone()[0]
    return inserted
def run(db):
    result=[]
    for code in COMPANIES:
        try:
            url,items=fetch(code); result.append({'code':code,'rows':insert(db,code,url,items),'latest':items[-1] if items else None,'status':'OK'})
        except Exception as exc: result.append({'code':code,'status':'ERROR','error':str(exc)})
    db.commit(); return result
if __name__=='__main__':
    db=sqlite3.connect(ROOT/'coal_network.db'); print(json.dumps(run(db),ensure_ascii=False,indent=2)); db.close()
