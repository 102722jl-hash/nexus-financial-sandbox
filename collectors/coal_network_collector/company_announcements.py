"""Rule-based parser and importer for thermal-power company disclosures."""
from __future__ import annotations
import argparse, hashlib, io, json, re, sqlite3, urllib.request
from datetime import datetime, timezone
from pathlib import Path
from pypdf import PdfReader

ROOT=Path(__file__).parent
COMPANIES={
 '600011.SH':'华能国际', '600027.SH':'华电国际', '600795.SH':'国电电力'
}

def now(): return datetime.now(timezone.utc).isoformat()
def pdf_text(body: bytes) -> str:
    reader=PdfReader(io.BytesIO(body)); pages=[]
    for no,page in enumerate(reader.pages,1): pages.append(f'\n[[PAGE:{no}]]\n'+(page.extract_text() or ''))
    return ''.join(pages)
def company_code(text):
    for code,name in COMPANIES.items():
        if name in text or code[:6] in text: return code
    return None
def published_date(text):
    found=re.findall(r'(20\d{2})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日',text)
    if not found: return None
    y,m,d=found[-1]; return f'{int(y):04d}-{int(m):02d}-{int(d):02d}'
def report_period(text):
    m=re.search(r'(20\d{2})\s*年\s*(上半年|下半年|第一季度|第二季度|第三季度|第四季度)',text)
    return f'{m.group(1)}-{m.group(2)}' if m else None
def page_at(text,position):
    pages=re.findall(r'\[\[PAGE:(\d+)\]\]',text[:position]); return pages[-1] if pages else 'unknown'
def parse_metrics(text):
    specs=[
      ('GRID_SALES_POWER','上网电量','亿千瓦时'),
      ('POWER_GENERATION','发电量','亿千瓦时'),
      ('ON_GRID_TARIFF','上网电价','元/兆瓦时'),
      ('ON_GRID_TARIFF','上网电价','元/千瓦时'),
      ('INSTALLED_CAPACITY','装机容量','万千瓦')]
    result=[]
    for code,label,unit in specs:
        pattern=rf'{label}[^。；;\n]{{0,55}}?([0-9][0-9,]*(?:\.[0-9]+)?)\s*{re.escape(unit)}'
        for i,m in enumerate(re.finditer(pattern,text)):
            result.append({'metric_code':code,'value':float(m.group(1).replace(',','')),'unit':unit,
              'quote':m.group(0).strip(),'locator':f'page:{page_at(text,m.start())};{label}:{i+1}'})
    return result

def download(db, code, url):
    if code not in COMPANIES: raise ValueError('unsupported company code')
    req=urllib.request.Request(url,headers={'User-Agent':'coal-network-collector/0.1'})
    with urllib.request.urlopen(req,timeout=45) as response:
        body=response.read(); ctype=response.headers.get('Content-Type',''); status=response.status
    digest=hashlib.sha256(body).hexdigest(); folder=ROOT/'raw'; folder.mkdir(exist_ok=True)
    path=folder/f'{digest}.pdf'; path.write_bytes(body); doc_id=f'company_{code}:{digest[:20]}'
    db.execute('INSERT OR IGNORE INTO raw_documents VALUES(?,?,?,?,?,?,?,?,?,?)',(doc_id,url,COMPANIES[code],now(),ctype,status,digest,str(path),'DOWNLOADED',None)); db.commit(); return doc_id

def import_pdf(db,row):
    doc_id,url,name,retrieved,sha,path=row; body=Path(path).read_bytes()
    try: text=pdf_text(body)
    except Exception as exc:
        db.execute("UPDATE raw_documents SET parse_status='ERROR',error_message=? WHERE document_id=?",(str(exc),doc_id)); return 0
    code=company_code(text); published=published_date(text); period=report_period(text); metrics=parse_metrics(text)
    if not code or not published or not metrics:
        reasons=[]
        if not code: reasons.append('ENTITY_CODE_MISSING')
        if not published: reasons.append('PUBLISHED_AT_MISSING')
        if not metrics: reasons.append('METRIC_NOT_FOUND_OR_SCANNED_PDF')
        db.execute("INSERT INTO review_queue(object_type,object_id,candidate_value,confidence,reason,evidence_ids,required_action,created_at) VALUES(?,?,?,?,?,?,?,?)",('COMPANY_PDF',doc_id,None,0.0,','.join(reasons),'[]','人工检查PDF文字和表格',now()))
        db.execute("UPDATE raw_documents SET parse_status='NEEDS_REVIEW' WHERE document_id=?",(doc_id,)); return 0
    count=0
    for item in metrics:
        ev='ev_'+hashlib.sha256(f"{doc_id}|{item['locator']}|{item['quote']}".encode()).hexdigest()[:24]
        db.execute("INSERT OR IGNORE INTO evidence(evidence_id,source_type,source_name,publisher,published_at,retrieved_at,original_quote,locator,source_url,data_cutoff,source_tier,temporal_role,snapshot_path,snapshot_sha256,supports_node_ids,acceptance_status,acceptance_reason) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(ev,'EXCHANGE_DISCLOSURE',name,name,published,retrieved,item['quote'],item['locator'],url,published,'T2','AS_OF_EVIDENCE',path,sha,'[]','ACCEPTED','GATES_PASSED'))
        mid='mv_'+hashlib.sha256(f"{code}|{item['metric_code']}|{period}|{item['value']}|{ev}".encode()).hexdigest()[:24]
        db.execute("INSERT OR IGNORE INTO metric_values(network_id,metric_value_id,metric_code,entity_code,value,unit,report_period,announcement_date,as_of_date,data_cutoff,value_status,evidence_id,source_table,source_column,source_row_key) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",('coal_power_v1',mid,item['metric_code'],code,item['value'],item['unit'],period,published,published,published,'SOURCE_FACT',ev,'company_announcement',item['metric_code'],doc_id)); count+=db.execute('SELECT changes()').fetchone()[0]
    db.execute("UPDATE raw_documents SET parse_status='PARSED' WHERE document_id=?",(doc_id,)); return count

def import_pending(db):
    rows=db.execute("SELECT document_id,source_url,source_name,retrieved_at,content_sha256,snapshot_path FROM raw_documents WHERE parse_status='DOWNLOADED' AND document_id LIKE 'company_%'").fetchall()
    count=sum(import_pdf(db,row) for row in rows); db.commit(); return len(rows),count

def main():
    p=argparse.ArgumentParser(); p.add_argument('command',choices=['download','import']); p.add_argument('--db',default=str(ROOT/'coal_network.db')); p.add_argument('--code'); p.add_argument('--url'); a=p.parse_args(); db=sqlite3.connect(a.db)
    if a.command=='download':
        if not a.code or not a.url: p.error('download requires --code and --url')
        print(json.dumps({'document_id':download(db,a.code,a.url)},ensure_ascii=False))
    else:
        docs,metrics=import_pending(db); print(f'documents={docs} metrics={metrics}')
    db.close()
if __name__=='__main__': main()
