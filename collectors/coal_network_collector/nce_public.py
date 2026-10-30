"""Collect publicly displayed coal indices from the National Coal Exchange.

This reads only the public page. It does not bypass login, captcha, or limits.
"""
from __future__ import annotations
import hashlib,re,sqlite3,urllib.request
from datetime import datetime,timezone
from pathlib import Path
from parsers import clean_html

ROOT=Path(__file__).parent
URL='https://www.ncexc.cn/mobile/'
SPECS=[('COAL_PRICE_5500','5500K'),('COAL_PRICE_5000','5000K'),('COAL_PRICE_4500','4500K')]
def now(): return datetime.now(timezone.utc).isoformat()
def fetch():
    req=urllib.request.Request(URL,headers={'User-Agent':'coal-network-collector/0.1'})
    with urllib.request.urlopen(req,timeout=30) as r: return r.read(),r.headers.get('Content-Type',''),r.status
def parse(text):
    out=[]
    date=re.search(r'(20\d{2})年\s*(\d{1,2})月\s*(\d{1,2})日',text)
    observed=f'{date.group(1)}-{int(date.group(2)):02d}-{int(date.group(3)):02d}' if date else None
    for code,label in SPECS:
        m=re.search(rf'{label}[^\d]{{0,40}}([0-9][0-9,]*(?:\.[0-9]+)?)\s*(?:元/?吨)?',text,re.I)
        if m: out.append((code,float(m.group(1).replace(',','')),observed,m.group(0)))
    return out
def run(db):
    try: body,ctype,status=fetch(); digest=hashlib.sha256(body).hexdigest(); raw=ROOT/'raw'; raw.mkdir(exist_ok=True); path=raw/f'nce-{digest}.html'; path.write_bytes(body); text=clean_html(body); values=parse(text)
    except Exception as exc:
        db.execute("INSERT INTO review_queue(object_type,object_id,candidate_value,confidence,reason,evidence_ids,required_action,created_at) VALUES(?,?,?,?,?,?,?,?)",('NCE_PAGE',URL,None,0.0,'ACCESS_ERROR','[]',str(exc),now())); db.commit(); return 0
    if not values:
        db.execute("INSERT INTO review_queue(object_type,object_id,candidate_value,confidence,reason,evidence_ids,required_action,created_at) VALUES(?,?,?,?,?,?,?,?)",('NCE_PAGE',URL,None,0.0,'PRICE_NOT_FOUND_OR_PAGE_CHANGED','[]','检查页面结构和公开许可',now())); db.commit(); return 0
    count=0
    for code,value,day,quote in values:
        if not day: continue
        eid='ev_'+hashlib.sha256(f'{URL}|{day}|{code}|{value}'.encode()).hexdigest()[:24]
        db.execute("INSERT OR IGNORE INTO evidence(evidence_id,source_type,source_name,publisher,published_at,retrieved_at,original_quote,locator,source_url,data_cutoff,source_tier,temporal_role,snapshot_path,snapshot_sha256,supports_node_ids,acceptance_status,acceptance_reason) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(eid,'PUBLIC_INDEX','全国煤炭交易中心','全国煤炭交易中心',day+'T23:59:00+08:00',now(),quote,f'text:{code}',URL,day,'T2','AS_OF_EVIDENCE',str(path),digest,'[]','ACCEPTED','GATES_PASSED'))
        mid='mv_'+hashlib.sha256(f'{code}|{day}|{value}|{eid}'.encode()).hexdigest()[:24]
        db.execute("INSERT OR IGNORE INTO metric_values(network_id,metric_value_id,metric_code,value,unit,as_of_date,data_cutoff,value_status,evidence_id,source_table,source_column,source_row_key) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",('coal_power_v1',mid,code,value,'元/吨',day,day,'SOURCE_FACT',eid,'nce_public',code,URL)); count+=db.execute('SELECT changes()').fetchone()[0]
    db.commit(); return count
if __name__=='__main__':
    db=sqlite3.connect(ROOT/'coal_network.db'); print('inserted='+str(run(db))); db.close()
