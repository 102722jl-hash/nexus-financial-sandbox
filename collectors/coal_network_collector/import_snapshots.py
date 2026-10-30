"""Parse downloaded snapshots, create evidence, and classify metric values."""
from __future__ import annotations
import argparse, hashlib, sqlite3, uuid
from datetime import datetime, timezone
from pathlib import Path
from parsers import PARSERS, clean_html, publication_date

ROOT=Path(__file__).parent
PUBLISHERS={'stats_energy':('国家统计局','T1'),'nea_power':('国家能源局','T1'),'ncexc_coal':('全国煤炭交易中心','T1')}

def now(): return datetime.now(timezone.utc).isoformat()

def import_document(db, row):
    document_id,url,source_name,retrieved_at,sha,path=row
    source_id=document_id.split(':',1)[0]
    parser=PARSERS.get(source_id)
    if not parser: return 0
    raw=Path(path).read_bytes(); text=clean_html(raw); published=publication_date(text)
    if not published:
        db.execute("INSERT INTO review_queue(object_type,object_id,candidate_value,confidence,reason,evidence_ids,required_action,created_at) VALUES(?,?,?,?,?,?,?,?)",('DOCUMENT',document_id,None,0.0,'PUBLISHED_AT_MISSING','[]','确认页面发布日期',now())); return 0
    publisher,tier=PUBLISHERS[source_id]; count=0
    for fact in parser(raw):
        evidence_id='ev_'+hashlib.sha256(f'{document_id}|{fact.locator}|{fact.original_quote}'.encode()).hexdigest()[:24]
        db.execute("INSERT OR IGNORE INTO evidence(evidence_id,source_type,source_name,publisher,published_at,retrieved_at,original_quote,locator,source_url,data_cutoff,source_tier,temporal_role,snapshot_path,snapshot_sha256,supports_node_ids,acceptance_status,acceptance_reason) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(evidence_id,'PUBLIC_WEB',source_name,publisher,published,retrieved_at,fact.original_quote,fact.locator,url,published,tier,'AS_OF_EVIDENCE',path,sha,'[]','ACCEPTED','GATES_PASSED'))
        metric_id='mv_'+hashlib.sha256(f'{fact.metric_code}|{fact.report_period}|{fact.value}|{evidence_id}'.encode()).hexdigest()[:24]
        db.execute("INSERT OR IGNORE INTO metric_values(network_id,metric_value_id,metric_code,value,unit,report_period,as_of_date,data_cutoff,value_status,evidence_id,source_table,source_column,source_row_key) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",('coal_power_v1',metric_id,fact.metric_code,fact.value,fact.unit,fact.report_period,published,published,'SOURCE_FACT',evidence_id,source_id,fact.metric_code,document_id)); count+=db.execute('SELECT changes()').fetchone()[0]
    db.execute("UPDATE raw_documents SET parse_status=? WHERE document_id=?",('PARSED' if count else 'NEEDS_REVIEW',document_id)); return count

def run(db):
    rows=db.execute("SELECT document_id,source_url,source_name,retrieved_at,content_sha256,snapshot_path FROM raw_documents WHERE parse_status='DOWNLOADED'").fetchall()
    total=sum(import_document(db,row) for row in rows); db.commit(); return len(rows),total

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--db',default=str(ROOT/'coal_network.db')); a=p.parse_args(); db=sqlite3.connect(a.db)
    docs,facts=run(db); db.close(); print(f'documents={docs} facts={facts}')
