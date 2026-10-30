"""Verify the exact model-facing PostgreSQL connection and row counts."""
import argparse,json,os
import psycopg
from psycopg import sql
TABLES=['network_registry','network_layers','network_nodes','network_edges','entities','metric_values','calculated_metric_lineage','metric_definitions','network_edge_templates','formulas','evidence','valuation','scenario_runs','scenario_values']
def main():
    p=argparse.ArgumentParser(); p.add_argument('--host',default='127.0.0.1'); p.add_argument('--port',type=int,default=5432); p.add_argument('--database',default='coal_network'); p.add_argument('--user',default='coal_network_readonly'); p.add_argument('--password-env',default='COAL_PG_READONLY_PASSWORD'); p.add_argument('--schema',default='coal_network'); a=p.parse_args(); password=os.environ.get(a.password_env)
    if not password: raise ValueError('missing environment variable: '+a.password_env)
    with psycopg.connect(host=a.host,port=a.port,dbname=a.database,user=a.user,password=password,sslmode='prefer',options='-c default_transaction_read_only=on') as conn:
        readonly=conn.execute('show transaction_read_only').fetchone()[0]; counts={}
        for table in TABLES: counts[table]=conn.execute(sql.SQL('select count(1) from {}.{}').format(sql.Identifier(a.schema),sql.Identifier(table))).fetchone()[0]
        print(json.dumps({'status':'READY_FOR_MODEL','transaction_read_only':readonly,'host':a.host,'port':a.port,'database':a.database,'schema':a.schema,'user':a.user,'counts':counts},ensure_ascii=False,indent=2))
if __name__=='__main__': main()
