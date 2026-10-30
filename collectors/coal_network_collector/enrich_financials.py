"""Second-pass financial enrichment for downloaded company PDFs."""
from __future__ import annotations
import hashlib,sqlite3
from datetime import datetime,timezone
from pathlib import Path
from company_announcements import pdf_text,company_code,published_date,report_period
from financial_reports import parse_financial_metrics,detect_currency_scale,scale_to_yuan

ROOT=Path(__file__).parent
def now(): return datetime.now(timezone.utc).isoformat()
def ensure(db):
    db.execute('CREATE TABLE IF NOT EXISTS document_processors(document_id TEXT,processor TEXT,processor_version TEXT,status TEXT,processed_at TEXT,error_message TEXT,PRIMARY KEY(document_id,processor,processor_version))'); db.commit()
def run(db):
    ensure(db); rows=db.execute("SELECT document_id,source_url,source_name,retrieved_at,content_sha256,snapshot_path FROM raw_documents WHERE document_id LIKE 'company_%' AND snapshot_path IS NOT NULL AND NOT EXISTS(SELECT 1 FROM document_processors p WHERE p.document_id=raw_documents.document_id AND p.processor='financials' AND p.processor_version='1')").fetchall(); inserted=0
    for doc,url,name,retrieved,sha,path in rows:
        try:
            text=pdf_text(Path(path).read_bytes()); code=company_code(text); published=published_date(text); period=report_period(text); scale=detect_currency_scale(text); facts=parse_financial_metrics(text)
            if not code or not published or not scale or not facts:
                db.execute("INSERT OR REPLACE INTO document_processors VALUES(?,?,?,?,?,?)",(doc,'financials','1','NEEDS_REVIEW',now(),'metadata, scale, or metrics missing')); continue
            for fact in facts:
                value=scale_to_yuan(fact['value'],scale); quote=fact['quote']+f'（原表单位：{scale}）'; ev='ev_'+hashlib.sha256(f"{doc}|financial|{fact['locator']}|{quote}".encode()).hexdigest()[:24]
                db.execute("INSERT OR IGNORE INTO evidence(evidence_id,source_type,source_name,publisher,published_at,retrieved_at,original_quote,locator,source_url,data_cutoff,source_tier,temporal_role,snapshot_path,snapshot_sha256,supports_node_ids,acceptance_status,acceptance_reason) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(ev,'EXCHANGE_DISCLOSURE',name,name,published,retrieved,quote,fact['locator'],url,published,'T2','AS_OF_EVIDENCE',path,sha,'[]','ACCEPTED','GATES_PASSED'))
                mid='mv_'+hashlib.sha256(f"{code}|{fact['metric_code']}|{period}|{value}|{ev}".encode()).hexdigest()[:24]
                db.execute("INSERT OR IGNORE INTO metric_values(network_id,metric_value_id,metric_code,entity_code,value,unit,currency,report_period,announcement_date,as_of_date,data_cutoff,value_status,evidence_id,source_table,source_column,source_row_key) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",('coal_power_v1',mid,fact['metric_code'],code,value,'元','CNY',period,published,published,published,'SOURCE_FACT',ev,'financial_report',fact['metric_code'],doc)); inserted+=db.execute('SELECT changes()').fetchone()[0]
            db.execute("INSERT OR REPLACE INTO document_processors VALUES(?,?,?,?,?,?)",(doc,'financials','1','PARSED',now(),None))
        except Exception as exc: db.execute("INSERT OR REPLACE INTO document_processors VALUES(?,?,?,?,?,?)",(doc,'financials','1','ERROR',now(),str(exc)))
    db.commit(); return len(rows),inserted
if __name__=='__main__':
    db=sqlite3.connect(ROOT/'coal_network.db'); docs,facts=run(db); db.close(); print(f'documents={docs} facts={facts}')
