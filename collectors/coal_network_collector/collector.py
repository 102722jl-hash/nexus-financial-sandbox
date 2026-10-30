"""规则驱动的煤炭网络采集基础设施。网络请求适配器应只返回标准化记录。"""
from __future__ import annotations
import argparse, hashlib, json, sqlite3, uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent
DB = ROOT / "coal_network.db"

def now(): return datetime.now(timezone.utc).isoformat()
def connect(path=DB):
    db = sqlite3.connect(path); db.execute("PRAGMA foreign_keys=ON"); return db
def init_db(path=DB):
    db = connect(path); db.executescript((ROOT/'schema.sql').read_text(encoding='utf-8')); db.commit(); db.close()
def content_hash(value): return hashlib.sha256(value.encode('utf-8')).hexdigest()

def seed(db):
    db.execute("INSERT OR IGNORE INTO network_registry VALUES (?,?,?,?,?,?,?)", ('coal_power_v1','煤炭价格到火电企业盈利传导','1.0.0','DRAFT','INDUSTRY_TRANSMISSION','2099-12-31T23:59:59+08:00',now()))
    layers=[(1,'macro_policy','宏观与政策','SOURCE'),(2,'coal_supply','煤炭供需','INTERMEDIATE'),(3,'coal_price','动力煤价格','INTERMEDIATE'),(4,'power_operation','火电经营','INTERMEDIATE'),(5,'company_finance','公司财务','INTERMEDIATE'),(6,'valuation','估值与市场表现','SINK')]
    for no,code,name,role in layers: db.execute("INSERT OR IGNORE INTO network_layers(network_id,layer_no,layer_code,layer_name_cn,path_role,sort_order,status,confidence) VALUES('coal_power_v1',?,?,?,?,?,'SOURCE_DEFINED',1)", (no,code,name,role,no))
    for code,name in [('600011.SH','华能国际'),('600027.SH','华电国际'),('600795.SH','国电电力')]: db.execute("INSERT OR IGNORE INTO entities VALUES('coal_power_v1',?,?,?,'POWER',?,'CN','THERMAL_POWER',NULL,'ACTIVE')",(code,name,'COMPANY',code[:6]+'.SH'))
    db.commit()

def ingest_metric(db, record):
    """写入已完成规则解析的记录；不接受缺少证据定位的事实。"""
    required=['metric_value_id','metric_code','unit','data_cutoff','evidence_id']
    missing=[k for k in required if not record.get(k)]
    if missing: raise ValueError('missing required fields: '+','.join(missing))
    db.execute("INSERT OR IGNORE INTO metric_values(network_id,metric_value_id,metric_code,node_id,entity_code,value,unit,currency,report_period,announcement_date,opdate,as_of_date,data_cutoff,value_status,evidence_id,source_table,source_column,source_row_key) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", tuple(record.get(k) for k in ['network_id','metric_value_id','metric_code','node_id','entity_code','value','unit','currency','report_period','announcement_date','opdate','as_of_date','data_cutoff','value_status','evidence_id','source_table','source_column','source_row_key']))

def main():
    p=argparse.ArgumentParser(); p.add_argument('command',choices=['init','seed']); p.add_argument('--db',default=str(DB)); a=p.parse_args()
    if a.command=='init': init_db(a.db)
    else:
        init_db(a.db); db=connect(a.db); seed(db); db.close()
if __name__=='__main__': main()
