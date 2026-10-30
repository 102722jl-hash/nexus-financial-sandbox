"""One-shot job intended for Windows Task Scheduler or cron."""
import json, sqlite3
from pathlib import Path
from collector import init_db, seed
from announcement_discovery import COMPANIES, discover, download_pending
from company_announcements import import_pending
from source_adapters import acquire_all
from import_snapshots import run as import_public

ROOT=Path(__file__).parent; db_path=ROOT/'coal_network.db'
init_db(db_path); db=sqlite3.connect(db_path); seed(db)
public=acquire_all(db)
for code in COMPANIES: discover(db,code)
downloaded=download_pending(db); public_docs,public_metrics=import_public(db); company_docs,company_metrics=import_pending(db)
print(json.dumps({'public_sources':public,'company_pdfs_downloaded':downloaded,
 'public_documents':public_docs,'public_metrics':public_metrics,
 'company_documents':company_docs,'company_metrics':company_metrics},ensure_ascii=False,indent=2))
db.close()
