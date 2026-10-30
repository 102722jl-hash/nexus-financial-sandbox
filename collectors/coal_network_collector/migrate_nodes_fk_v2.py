"""Transactional repair of the network_nodes entity foreign key."""
from pathlib import Path
import shutil, sqlite3

ROOT=Path(__file__).parent; path=ROOT/'coal_network.db'; backup=ROOT/'coal_network.pre_nodes_fk.db'
shutil.copy2(path,backup)
db=sqlite3.connect(path)
try:
    db.execute('PRAGMA foreign_keys=OFF'); db.execute('BEGIN IMMEDIATE')
    db.execute('ALTER TABLE network_nodes RENAME TO network_nodes_old')
    db.execute('''CREATE TABLE network_nodes (
      network_id TEXT NOT NULL, node_id TEXT NOT NULL, layer_no INTEGER NOT NULL,
      node_name_cn TEXT NOT NULL, node_description TEXT, node_type TEXT NOT NULL,
      metric_code TEXT, metric_name TEXT, metric_type TEXT, unit TEXT, currency TEXT,
      baseline_value TEXT, editable INTEGER NOT NULL DEFAULT 0, value_status TEXT NOT NULL,
      entity_code TEXT, evidence_id TEXT, data_cutoff TEXT NOT NULL, status TEXT NOT NULL,
      PRIMARY KEY(network_id,node_id),
      FOREIGN KEY(network_id,layer_no) REFERENCES network_layers(network_id,layer_no),
      FOREIGN KEY(network_id,entity_code) REFERENCES entities(network_id,entity_code),
      FOREIGN KEY(evidence_id) REFERENCES evidence(evidence_id))''')
    cols='network_id,node_id,layer_no,node_name_cn,node_description,node_type,metric_code,metric_name,metric_type,unit,currency,baseline_value,editable,value_status,entity_code,evidence_id,data_cutoff,status'
    db.execute(f'INSERT INTO network_nodes({cols}) SELECT {cols} FROM network_nodes_old')
    db.execute('DROP TABLE network_nodes_old'); db.commit(); db.execute('PRAGMA foreign_keys=ON')
    violations=db.execute('PRAGMA foreign_key_check').fetchall()
    if violations: raise RuntimeError(f'foreign key violations: {violations}')
    print(f'migration complete; backup={backup}; nodes={db.execute("SELECT COUNT(*) FROM network_nodes").fetchone()[0]}')
except Exception:
    db.rollback(); raise
finally: db.close()
