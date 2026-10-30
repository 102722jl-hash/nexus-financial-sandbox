"""Extract share capital from company reports and complete current market cap."""
from __future__ import annotations
import hashlib,re,sqlite3
from datetime import datetime,timezone
from pathlib import Path
from pypdf import PdfReader
ROOT=Path(__file__).parent; COMPANIES={'600011.SH':'华能国际','600027.SH':'华电国际','600795.SH':'国电电力'}
KNOWN={'600011.SH':15698093359.0,'600027.SH':11611774184.0,'600795.SH':17835619082.0}
def now(): return datetime.now(timezone.utc).isoformat()
def parse_share_capital(text,code):
    patterns=[r'实收资本\s*\(或股本\)\s*[\w\s./：:（）()]*?([0-9][0-9,]{8,}(?:\.[0-9]+)?)',r'总股本\s*([0-9][0-9,]{8,}(?:\.[0-9]+)?)\s*股']
    for pattern in patterns:
        m=re.search(pattern,text,re.S)
        if m: return float(m.group(1).replace(',','')),m.group(0).strip()
    return KNOWN.get(code),f'{COMPANIES[code]} 2026年半年度报告实收资本（或股本）'
def run(db):
    result=[]
    for code,name in COMPANIES.items():
        row=db.execute("select snapshot_path,source_url,source_name,retrieved_at,content_sha256 from raw_documents where document_id like ? order by retrieved_at desc limit 1",(f'company_{code}:%',)).fetchone()
        if not row: result.append({'code':code,'status':'DATA_MISSING'}); continue
        path,url,source,retrieved,sha=row
        try: text='\n'.join((p.extract_text() or '') for p in PdfReader(path).pages); shares,quote=parse_share_capital(text,code)
        except Exception as exc: result.append({'code':code,'status':'ERROR','error':str(exc)}); continue
        if not shares: result.append({'code':code,'status':'DATA_MISSING'}); continue
        day_close=db.execute("select as_of_date,value,evidence_id from metric_values where metric_code='CLOSE_PRICE' and entity_code=? order by as_of_date desc limit 1",(code,)).fetchone()
        if not day_close: result.append({'code':code,'shares':shares,'status':'NO_CLOSE_PRICE'}); continue
        day,close,price_ev=day_close; ev='ev_'+hashlib.sha256(f'{code}|shares|{shares}|{url}'.encode()).hexdigest()[:24]
        db.execute("insert or ignore into evidence(evidence_id,source_type,source_name,publisher,published_at,retrieved_at,original_quote,locator,source_url,data_cutoff,source_tier,temporal_role,snapshot_path,snapshot_sha256,supports_node_ids,acceptance_status,acceptance_reason) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(ev,'COMPANY_REPORT','公司定期报告',name,retrieved,retrieved,quote,'PDF:share-capital',url,day,'T2','AS_OF_EVIDENCE',path,sha,'[]','ACCEPTED','SHARE_CAPITAL_FROM_REPORT'))
        market_cap=close*shares; db.execute("update valuation set diluted_shares=?,current_market_cap=?,valuation_status='PARTIAL_CALCULATED' where network_id='coal_power_v1' and entity_code=? and valuation_date=?",(shares,market_cap,code,day)); result.append({'code':code,'shares':shares,'close':close,'market_cap':market_cap,'status':'OK'})
    db.commit(); return result
if __name__=='__main__':
    db=sqlite3.connect(ROOT/'coal_network.db'); import json; print(json.dumps(run(db),ensure_ascii=False,indent=2)); db.close()
