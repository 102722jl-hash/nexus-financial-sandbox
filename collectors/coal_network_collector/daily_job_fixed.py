"""Corrected one-shot daily collection job."""
import json,sqlite3
from pathlib import Path
from collector import init_db,seed
from announcement_discovery_fixed import COMPANIES,discover,download_pending
from company_announcements import import_pending
from source_adapters import acquire_all
from import_snapshots import run as import_public

ROOT=Path(__file__).parent; path=ROOT/'coal_network.db'; init_db(path); db=sqlite3.connect(path); seed(db)
public=acquire_all(db); discovered={code:len(discover(db,code)) for code in COMPANIES}; downloaded=download_pending(db)
public_docs,public_metrics=import_public(db); company_docs,company_metrics=import_pending(db)
print(json.dumps({'public_sources':public,'announcements_discovered':discovered,'company_pdfs_downloaded':downloaded,'public_documents':public_docs,'public_metrics':public_metrics,'company_documents':company_docs,'company_metrics':company_metrics},ensure_ascii=False,indent=2)); db.close()
