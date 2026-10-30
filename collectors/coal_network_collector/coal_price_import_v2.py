"""Contract-v2 importer for authorized CCTD coal price CSV exports."""
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
        if not {'date','source_url'}.issubset(names): raise ValueError('CSV必须包含 date, source_url')
        available=[x for x in FIELDS if x in names]
        if not available: raise ValueError('CSV至少需要 price_5500/5000/4500 之一')
        for row_no,row in enumerate(reader,2):
            day=datetime.strptime(row['date'].strip(),'%Y-%m-%d').date().isoformat()
            for column in available:
                raw=(row.get(column) or '').strip()
                if not raw: continue
                value=float(raw.replace(',','')); code,label=FIELDS[column]; locator=f'csv:row:{row_no};column:{column}'; quote=f'CCTD {day} {label}={value} 元/吨'; eid='ev_'+hashlib.sha256((row['source_url']+'|'+quote).encode()).hexdigest()[:24]
                db.execute("INSERT OR IGNORE INTO evidence(evidence_id,source_type,source_name,publisher,published_at,retrieved_at,original_quote,page_or_locator,locator,source_url,anchor_at,declared_role,data_cutoff,source_tier,temporal_role,raw_storage_status,supports_node_ids,acceptance_status,review_status,acceptance_reason,source_table,source_column,source_row_key) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(eid,'AUTHORIZED_DATA_EXPORT','CCTD煤炭市场网','CCTD',day+'T23:59:00+08:00',now(),quote,locator,locator,row['source_url'],day,'AS_OF_EVIDENCE',day,'T2','AS_OF_EVIDENCE','NOT_STORED_BY_POLICY','[]','ACCEPTED','ACCEPTED','GATES_PASSED','cctd_csv',column,str(row_no)))
                if not db.execute('select 1 from evidence where evidence_id=?',(eid,)).fetchone(): raise RuntimeError('evidence insert failed: '+eid)
                mid='mv_'+hashlib.sha256((code+'|'+day+'|'+str(value)+'|'+eid).encode()).hexdigest()[:24]
                db.execute("INSERT OR IGNORE INTO metric_values(network_id,metric_value_id,metric_code,value,unit,as_of_date,data_cutoff,value_status,evidence_id,source_table,source_column,source_row_key) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",('coal_power_v1',mid,code,value,'元/吨',day,day,'SOURCE_FACT',eid,'cctd_csv',column,str(row_no))); inserted+=db.execute('select changes()').fetchone()[0]
    db.commit(); return inserted
if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('csv'); p.add_argument('--db',default=str(ROOT/'coal_network.db')); a=p.parse_args(); db=sqlite3.connect(a.db); db.execute('pragma foreign_keys=on'); print('inserted='+str(import_csv(db,a.csv))); db.close()
