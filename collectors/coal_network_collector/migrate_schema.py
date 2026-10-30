"""Repair constraints needed by SQLite composite foreign keys."""
import sqlite3
from pathlib import Path

db=sqlite3.connect(Path(__file__).parent/'coal_network.db')
db.execute('CREATE UNIQUE INDEX IF NOT EXISTS ux_entities_network_code ON entities(network_id, entity_code)')
db.commit(); db.close(); print('schema migration complete')
