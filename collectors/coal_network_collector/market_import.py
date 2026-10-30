"""Import licensed daily market CSV data with strict field validation."""
from __future__ import annotations
import argparse,csv,hashlib,sqlite3
from datetime import date
from pathlib import Path

ROOT=Path(__file__).parent
REQUIRED={'entity_code','trade_date','close_price','currency','source_url'}

def import_csv(db,path):
    inserted=0
    with open(path,encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f)
        missing=REQUIRED-set(reader.fieldnames or [])
        if missing: raise ValueError('missing columns: '+','.join(sorted(missing)))
        for no,row in enumerate(reader,2):
            code=row['entity_code']; day=date.fromisoformat(row['trade_date']).isoformat(); price=float(row['close_price'])
            if code not in {'600011.SH','600027.SH','600795.SH'} or price<=0: raise ValueError(f'invalid row {no}')
            quote=f"{code} {day} close={price} {row['currency']}"
            eid='ev_'+hashlib.sha256((row['source_url']+'|'+quote).encode()).hexdigest()[:24]
            db.execute("INSERT OR IGNORE INTO evidence(evidence_id,source_type,source_name,publisher,published_at,retrieved_at,original_quote,locator,source_url,data_cutoff,source_tier,temporal_role,supports_node_ids,acceptance_status,acceptance_reason) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(eid,'LICENSED_MARKET_DATA',row.get('source_name') or 'market_csv',row.get('publisher') or 'licensed_provider',day+'T15:00:00+08:00',day+'T15:00:00+08:00',quote,f'csv:row:{no}',row['source_url'],day,'T2','POST_EVENT_VALIDATION','[]','ACCEPTED','GATES_PASSED'))
            mid='mv_'+hashlib.sha256((code+'|'+day+'|'+str(price)+'|'+eid).encode()).hexdigest()[:24]
            db.execute("INSERT OR IGNORE INTO metric_values(network_id,metric_value_id,metric_code,entity_code,value,unit,currency,as_of_date,data_cutoff,value_status,evidence_id,source_table,source_column,source_row_key) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",('coal_power_v1',mid,'CLOSE_PRICE',code,price,row['currency']+'/股',row['currency'],day,day,'SOURCE_FACT',eid,'market_csv','close_price',str(no))); inserted+=db.execute('SELECT changes()').fetchone()[0]
    db.commit(); return inserted

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('csv'); p.add_argument('--db',default=str(ROOT/'coal_network.db')); a=p.parse_args(); db=sqlite3.connect(a.db); print('inserted='+str(import_csv(db,a.csv))); db.close()
