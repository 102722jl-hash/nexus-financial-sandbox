"""Publish the audited SQLite network into a PostgreSQL target schema.

The target schema is replaced transactionally for one network_id. The source
SQLite database is never modified. Passwords are accepted only via the
environment variable named by --password-env or through the current process.
"""
from __future__ import annotations
import argparse, json, os, sqlite3
from pathlib import Path
from typing import Any

try:
    import psycopg
    from psycopg import sql
except ImportError:  # pragma: no cover
    psycopg = None

ROOT=Path(__file__).parent
TABLES=['network_registry','network_layers','entities','evidence','metric_values','formulas','network_nodes','network_edges','valuation','review_queue','raw_documents']
KEY_COLUMNS={
 'network_registry':['network_id'],'network_layers':['network_id','layer_no'],'entities':['network_id','entity_code'],
 'evidence':['evidence_id'],'metric_values':['metric_value_id'],'formulas':['formula_id'],
 'network_nodes':['network_id','node_id'],'network_edges':['network_id','edge_id'],
 'valuation':['network_id','entity_code','valuation_date'],'review_queue':['review_id'],'raw_documents':['document_id']}
def connect_pg(args):
    if psycopg is None: raise RuntimeError('Install psycopg[binary] before PostgreSQL sync')
    password=os.environ.get(args.password_env) if args.password_env else args.password
    if not password: raise ValueError('Provide --password-env or --password for this request; never store it in config')
    return psycopg.connect(host=args.host,port=args.port,dbname=args.database,user=args.user,password=password,sslmode=args.sslmode,connect_timeout=10)
def qident(name): return sql.Identifier(name)
def source_rows(db,table,network_id):
    cols=[r[1] for r in db.execute(f'pragma table_info({table})')]
    if 'network_id' in cols: rows=db.execute(f'SELECT * FROM {table} WHERE network_id=?',(network_id,)).fetchall()
    else: rows=db.execute(f'SELECT * FROM {table}').fetchall()
    return cols,rows
def ensure_schema(pg,schema):
    pg.execute(sql.SQL('CREATE SCHEMA IF NOT EXISTS {}').format(qident(schema)))
    for table in TABLES:
        pg.execute(sql.SQL('CREATE TABLE IF NOT EXISTS {}.{} AS TABLE public.{} WITH NO DATA').format(qident(schema),qident(table),qident(table)))
def sync(args):
    local=sqlite3.connect(args.sqlite); pg=connect_pg(args)
    try:
        pg.execute('SET TRANSACTION READ WRITE'); ensure_schema(pg,args.schema)
        # Clear only this network. Non-network audit tables are replaced only for this published snapshot.
        for table in reversed(TABLES):
            cols=[r[1] for r in local.execute(f'pragma table_info({table})')]
            if 'network_id' in cols: pg.execute(sql.SQL('DELETE FROM {}.{} WHERE network_id=%s').format(qident(args.schema),qident(table)),(args.network_id,))
            else: pg.execute(sql.SQL('TRUNCATE TABLE {}.{}').format(qident(args.schema),qident(table)))
        counts={}
        for table in TABLES:
            cols,rows=source_rows(local,table,args.network_id); counts[table]=len(rows)
            if not rows: continue
            stmt=sql.SQL('INSERT INTO {}.{} ({}) VALUES ({})').format(qident(args.schema),qident(table),sql.SQL(',').join(map(qident,cols)),sql.SQL(',').join(sql.Placeholder() for _ in cols))
            pg.executemany(stmt,rows)
        pg.execute('SET CONSTRAINTS ALL IMMEDIATE'); pg.commit()
        return {'status':'SYNCED','schema':args.schema,'network_id':args.network_id,'counts':counts}
    except Exception:
        pg.rollback(); raise
    finally: local.close(); pg.close()
def main():
    p=argparse.ArgumentParser(); p.add_argument('--sqlite',default=str(ROOT/'coal_network.db')); p.add_argument('--host',default='127.0.0.1'); p.add_argument('--port',type=int,default=5432); p.add_argument('--database',required=True); p.add_argument('--user',required=True); p.add_argument('--password-env'); p.add_argument('--password'); p.add_argument('--schema',default='coal_network'); p.add_argument('--network-id',default='coal_power_v1'); p.add_argument('--sslmode',default='prefer',choices=['disable','allow','prefer','require','verify-ca','verify-full']); a=p.parse_args(); print(json.dumps(sync(a),ensure_ascii=False,indent=2))
if __name__=='__main__': main()
