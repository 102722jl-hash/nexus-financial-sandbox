"""Import CCTD/authorized coal-price CSV into the network database.

Expected columns: date, price_5500, price_5000, price_4500, source_url.
The CSV must come from a permitted export/API; this script does not bypass
login, captcha, paywalls, or site controls.
"""
from __future__ import annotations
import argparse,csv,hashlib,sqlite3
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).parent
FIELDS={'price_5500':('COAL_PRICE_5500','5500大卡'),'price_5000':('COAL_PRICE_5000','5000大卡'),'price_4500':('COAL_PRICE_4500','4500大卡')}
def now(): return datetime.now(timezone.utc).isoformat()
def import_csv(db,path):
    inserted=0
    with open(path,encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f); names=set(reader.fieldnames or [])
        required={'date','source_url'}
        if not required.issubset(names): raise ValueError('CSV必须包含 date, source_url')
        available=[x for x in FIELDS if x in names]
        if not available: raise ValueError('CSV至少需要 price_5500/5000/4500 之一')
        for row_no,row in enumerate(reader,2):
            day=datetime.strptime(row['date'].strip(),'%Y-%m-%d').date().isoformat()
            for column in available:
                raw=(row.get(column) or '').strip()
                if not raw: continue
                value=float(raw.replace(',','')); code,label=FIELDS[column]
                quote=f'CCTD {day} {label}={value} 元/吨'; eid='ev_'+hashlib.sha256((row['source_url']+'|'+quote).encode()).hexdigest()[:24]
                db.execute("INSERT OR IGNORE INTO evidence(evidence_id,source_type,source_name,publisher,published_at,retrieved_at,original_quote,locator,source_url,data_cutoff,source_tier,temporal_role,supports_node_ids,acceptance_status,acceptance_reason) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(eid,'AUTHORIZED_DATA_EXPORT','CCTD煤炭市场网','CCTD',day+'T23:59:00+08:00',now(),quote,f'csv:row:{row_no};column:{column}',row['source_url'],day,'T2','AS_OF_EVIDENCE','[]','ACCEPTED','GATES_PASSED'))
                mid='mv_'+hashlib.sha256((code+'|'+day+'|'+str(value)+'|'+eid).encode()).hexdigest()[:24]
                db.execute("INSERT OR IGNORE INTO metric_values(network_id,metric_value_id,metric_code,value,unit,as_of_date,data_cutoff,value_status,evidence_id,source_table,source_column,source_row_key) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",('coal_power_v1',mid,code,value,'元/吨',day,day,'SOURCE_FACT',eid,'cctd_csv',column,str(row_no))); inserted+=db.execute('SELECT changes()').fetchone()[0]
    db.commit(); return inserted
if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('csv'); p.add_argument('--db',default=str(ROOT/'coal_network.db')); a=p.parse_args(); db=sqlite3.connect(a.db); print('inserted='+str(import_csv(db,a.csv))); db.close()
