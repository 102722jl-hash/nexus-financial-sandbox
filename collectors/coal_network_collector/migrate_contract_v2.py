"""Upgrade an existing database to the complete network data contract."""
from __future__ import annotations
import shutil, sqlite3
from datetime import datetime
from pathlib import Path

ROOT=Path(__file__).parent; DB=ROOT/'coal_network.db'
def column(db,table,name): return any(r[1]==name for r in db.execute(f'pragma table_info({table})'))
def add(db,table,name,definition):
    if not column(db,table,name): db.execute(f'alter table {table} add column {name} {definition}')
def migrate():
    backup=ROOT/f'coal_network.before_contract_{datetime.now():%Y%m%d_%H%M%S}.db'; shutil.copy2(DB,backup)
    db=sqlite3.connect(DB); db.execute('pragma foreign_keys=off'); db.execute('begin immediate')
    try:
        for n,d in [('page_or_locator',"TEXT NOT NULL DEFAULT ''"),('anchor_at','TEXT'),('declared_role','TEXT'),('raw_storage_status',"TEXT NOT NULL DEFAULT 'STORED'"),('review_status',"TEXT NOT NULL DEFAULT 'PENDING'"),('source_table','TEXT'),('source_column','TEXT'),('source_row_key','TEXT')]: add(db,'evidence',n,d)
        db.execute("update evidence set page_or_locator=coalesce(locator,''),anchor_at=coalesce(anchor_at,data_cutoff),declared_role=case when temporal_role='POST_EVENT_VALIDATION' then 'POST_EVENT_VALIDATION' else 'AS_OF_EVIDENCE' end,review_status=case when acceptance_status='ACCEPTED' then 'ACCEPTED' else 'PENDING' end where page_or_locator=''")
        add(db,'network_edges','parameters_json',"TEXT NOT NULL DEFAULT '{}'")
        db.execute('create unique index if not exists ux_entities_network_code on entities(network_id,entity_code)')
        db.execute('alter table network_edges rename to network_edges_old')
        db.execute("""create table network_edges(network_id TEXT NOT NULL,edge_id TEXT NOT NULL,source_node_id TEXT NOT NULL,target_node_id TEXT NOT NULL,direction TEXT NOT NULL,relation_type TEXT NOT NULL,formula_id TEXT,formula_type TEXT,weight REAL,lag_days INTEGER,impact_cap_pct REAL,confidence REAL,mechanism TEXT,parameter_status TEXT,evidence_id TEXT,evidence_source TEXT,parameters_json TEXT NOT NULL DEFAULT '{}',status TEXT NOT NULL,primary key(network_id,edge_id),foreign key(network_id,source_node_id) references network_nodes(network_id,node_id),foreign key(network_id,target_node_id) references network_nodes(network_id,node_id),foreign key(formula_id) references formulas(formula_id),foreign key(evidence_id) references evidence(evidence_id))""")
        db.execute("insert into network_edges(network_id,edge_id,source_node_id,target_node_id,direction,relation_type,formula_id,formula_type,weight,lag_days,impact_cap_pct,confidence,mechanism,parameter_status,evidence_id,evidence_source,parameters_json,status) select network_id,edge_id,source_node_id,target_node_id,direction,relation_type,formula_id,formula_type,weight,lag_days,impact_cap_pct,confidence,mechanism,parameter_status,evidence_id,evidence_source,coalesce(parameters_json,'{}'),status from network_edges_old")
        db.execute('drop table network_edges_old'); db.commit(); db.execute('pragma foreign_keys=on')
        errors=db.execute('pragma foreign_key_check').fetchall()
        if errors: raise RuntimeError(f'foreign key violations: {errors}')
        print(f'contract migration complete; backup={backup}')
    except Exception:
        db.rollback(); raise
    finally: db.close()
if __name__=='__main__': migrate()
