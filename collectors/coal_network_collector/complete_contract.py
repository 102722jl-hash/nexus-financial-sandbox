"""Complete remaining contract metadata without fabricating market values."""
from __future__ import annotations
import json,sqlite3
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).parent; DB=ROOT/'coal_network.db'
def install_evidence_defaults(db):
    db.execute('''CREATE TRIGGER IF NOT EXISTS trg_evidence_contract_defaults
    AFTER INSERT ON evidence FOR EACH ROW BEGIN
      UPDATE evidence SET page_or_locator=CASE WHEN page_or_locator='' THEN COALESCE(locator,'') ELSE page_or_locator END,
        anchor_at=COALESCE(anchor_at,data_cutoff),
        declared_role=COALESCE(declared_role,CASE WHEN temporal_role='POST_EVENT_VALIDATION' THEN 'POST_EVENT_VALIDATION' ELSE 'AS_OF_EVIDENCE' END),
        review_status=CASE WHEN review_status='PENDING' AND acceptance_status='ACCEPTED' THEN 'ACCEPTED' ELSE review_status END,
        raw_storage_status=COALESCE(raw_storage_status,CASE WHEN snapshot_path IS NULL THEN 'NOT_STORED_BY_POLICY' ELSE 'STORED' END)
      WHERE evidence_id=NEW.evidence_id;
    END''')
def build_baselines(db):
    rows=db.execute("SELECT node_id,metric_code,entity_code,unit FROM network_nodes WHERE metric_code IS NOT NULL").fetchall(); updated=0
    for node,metric,entity,unit in rows:
        where='metric_code=? AND entity_code IS ?'; params=(metric,entity)
        latest=db.execute(f"SELECT value,as_of_date,evidence_id FROM metric_values WHERE {where} AND value IS NOT NULL ORDER BY COALESCE(as_of_date,report_period,data_cutoff) DESC LIMIT 1",params).fetchone()
        if not latest: continue
        value,day,evidence=latest; baseline=json.dumps({'BASE':value,'as_of_date':day,'evidence_id':evidence},ensure_ascii=False)
        editable=1 if metric.startswith('COAL_PRICE') or metric in ('POWER_CONSUMPTION','POWER_GENERATION','GRID_SALES_POWER','ON_GRID_TARIFF') else 0
        db.execute("UPDATE network_nodes SET baseline_value=?,editable=?,value_status='SOURCE_FACT',evidence_id=?,data_cutoff=? WHERE node_id=?",(baseline,editable,evidence,day or datetime.now(timezone.utc).date().isoformat(),node)); updated+=db.execute('SELECT changes()').fetchone()[0]
    return updated
def build_valuation(db):
    rows=db.execute("SELECT entity_code,MAX(as_of_date) FROM metric_values WHERE metric_code='CLOSE_PRICE' AND entity_code IS NOT NULL GROUP BY entity_code").fetchall(); written=0
    for entity,day in rows:
        close=db.execute("SELECT value,evidence_id FROM metric_values WHERE metric_code='CLOSE_PRICE' AND entity_code=? AND as_of_date=? ORDER BY metric_value_id DESC LIMIT 1",(entity,day)).fetchone()
        if not close: continue
        value,evidence=close; db.execute("INSERT OR IGNORE INTO valuation(network_id,entity_code,valuation_date,price_asof,close_price,data_cutoff,valuation_status,evidence_id) VALUES(?,?,?,?,?,?,?,?)",('coal_power_v1',entity,day,day,value,day,'DATA_MISSING',evidence)); written+=db.execute('SELECT changes()').fetchone()[0]
    return written
def main():
    db=sqlite3.connect(DB); db.execute('PRAGMA foreign_keys=ON'); install_evidence_defaults(db); baselines=build_baselines(db); valuations=build_valuation(db); db.commit(); db.close(); print(json.dumps({'baseline_nodes_updated':baselines,'valuation_rows_added':valuations},ensure_ascii=False))
if __name__=='__main__': main()
