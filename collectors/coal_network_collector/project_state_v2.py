"""Synchronize cutoff and summarize auditable project state."""
import sqlite3
from pathlib import Path
ROOT=Path(__file__).parent
def sync_cutoff(db):
    dates=[r[0] for r in db.execute("SELECT data_cutoff FROM metric_values WHERE data_cutoff IS NOT NULL AND data_cutoff<>''")]
    dates += [r[0] for r in db.execute("SELECT substr(published_at,1,10) FROM evidence WHERE published_at IS NOT NULL AND published_at<>''")]
    cutoff=max((x[:10] for x in dates if len(x)>=10 and x[:4].isdigit()),default=None)
    if cutoff: db.execute("UPDATE network_registry SET data_cutoff=? WHERE network_id='coal_power_v1'",(cutoff,)); db.commit()
    return cutoff
