"""Compatibility fix for announcement catalogue insertion and run IDs."""
import sqlite3, uuid
from announcement_discovery import ENDPOINT, now, normalize, request_page, ensure_tables, download_pending, COMPANIES

def discover(db,code):
    ensure_tables(db); run_id=f'{code}:{uuid.uuid4().hex}'
    try:
        items=normalize(code,request_page(code))
        db.execute('INSERT INTO discovery_runs VALUES(?,?,?,?,?,?,?)',(run_id,ENDPOINT,code,now(),len(items),'SUCCESS',None))
        for item in items:
            db.execute('INSERT OR IGNORE INTO announcement_catalogue VALUES(?,?,?,?,?,?,?,?,?)',(item['announcement_id'],code,item['title'],item['published_ms'],item['url'],now(),None,'DISCOVERED',None))
        db.commit(); return items
    except Exception as exc:
        db.execute('INSERT INTO discovery_runs VALUES(?,?,?,?,?,?,?)',(run_id,ENDPOINT,code,now(),None,'ERROR',str(exc))); db.commit(); return []
