"""Discover new company PDFs from CNINFO's public announcement catalogue."""
from __future__ import annotations
import argparse, json, sqlite3, urllib.parse, urllib.request
from datetime import datetime, timezone
from pathlib import Path
from company_announcements import COMPANIES, download

ROOT=Path(__file__).parent
ENDPOINT='https://www.cninfo.com.cn/new/hisAnnouncement/query'
ORGS={'600011.SH':'gssh0600011','600027.SH':'gssh0600027','600795.SH':'gssh0600795'}
KEYWORDS=('发电量','上网电量','上网电价','经营数据','年度报告','半年度报告','季度报告')

def now(): return datetime.now(timezone.utc).isoformat()
def request_page(code,page=1,page_size=30):
    symbol=code[:6]
    form={'pageNum':str(page),'pageSize':str(page_size),'column':'sse','tabName':'fulltext',
          'plate':'sh','stock':f'{symbol},{ORGS[code]}','searchkey':'','secid':'',
          'category':'','trade':'','seDate':'','sortName':'','sortType':'','isHLtitle':'true'}
    body=urllib.parse.urlencode(form).encode()
    req=urllib.request.Request(ENDPOINT,data=body,headers={
      'User-Agent':'Mozilla/5.0 coal-network-collector/0.1','Referer':'https://www.cninfo.com.cn/',
      'Content-Type':'application/x-www-form-urlencoded; charset=UTF-8'})
    with urllib.request.urlopen(req,timeout=30) as response: return json.loads(response.read().decode('utf-8'))

def normalize(code,payload):
    out=[]
    for item in payload.get('announcements') or []:
        title=(item.get('announcementTitle') or '').replace('<em>','').replace('</em>','')
        if not any(word in title for word in KEYWORDS): continue
        adjunct=item.get('adjunctUrl') or ''
        if not adjunct.lower().endswith('.pdf'): continue
        out.append({'code':code,'announcement_id':str(item.get('announcementId') or adjunct),
          'title':title,'published_ms':item.get('announcementTime'),
          'url':'https://static.cninfo.com.cn/'+adjunct.lstrip('/')})
    return out

def ensure_tables(db):
    db.executescript('''
    CREATE TABLE IF NOT EXISTS announcement_catalogue(
      announcement_id TEXT PRIMARY KEY, entity_code TEXT NOT NULL, title TEXT NOT NULL,
      published_ms INTEGER, pdf_url TEXT NOT NULL, discovered_at TEXT NOT NULL,
      document_id TEXT, status TEXT NOT NULL, error_message TEXT);
    CREATE TABLE IF NOT EXISTS discovery_runs(
      discovery_id TEXT PRIMARY KEY, query_url TEXT NOT NULL, entity_code TEXT NOT NULL,
      queried_at TEXT NOT NULL, result_count INTEGER, status TEXT NOT NULL, error_message TEXT);
    '''); db.commit()

def discover(db,code):
    ensure_tables(db); run_id=f'{code}:{datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")}'
    try:
        items=normalize(code,request_page(code))
        db.execute('INSERT INTO discovery_runs VALUES(?,?,?,?,?,?,?)',(run_id,ENDPOINT,code,now(),len(items),'SUCCESS',None))
        for item in items:
            db.execute('INSERT OR IGNORE INTO announcement_catalogue VALUES(?,?,?,?,?,?,?,?)',(item['announcement_id'],code,item['title'],item['published_ms'],item['url'],now(),None,'DISCOVERED',None))
        db.commit(); return items
    except Exception as exc:
        db.execute('INSERT INTO discovery_runs VALUES(?,?,?,?,?,?,?)',(run_id,ENDPOINT,code,now(),None,'ERROR',str(exc))); db.commit(); return []

def download_pending(db):
    ensure_tables(db); rows=db.execute("SELECT announcement_id,entity_code,pdf_url FROM announcement_catalogue WHERE status='DISCOVERED'").fetchall(); done=0
    for announcement_id,code,url in rows:
        try:
            doc_id=download(db,code,url); db.execute("UPDATE announcement_catalogue SET document_id=?,status='DOWNLOADED' WHERE announcement_id=?",(doc_id,announcement_id)); done+=1
        except Exception as exc:
            db.execute("UPDATE announcement_catalogue SET status='ERROR',error_message=? WHERE announcement_id=?",(str(exc),announcement_id))
    db.commit(); return done

def main():
    p=argparse.ArgumentParser(); p.add_argument('--db',default=str(ROOT/'coal_network.db')); p.add_argument('--code',choices=[*COMPANIES,'all'],default='all'); p.add_argument('--download',action='store_true'); a=p.parse_args(); db=sqlite3.connect(a.db)
    codes=COMPANIES if a.code=='all' else [a.code]; result={code:len(discover(db,code)) for code in codes}
    if a.download: result['downloaded']=download_pending(db)
    print(json.dumps(result,ensure_ascii=False,indent=2)); db.close()
if __name__=='__main__': main()
