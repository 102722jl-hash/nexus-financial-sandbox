"""Refresh read-only grants after new target tables are created."""
import argparse,os
import psycopg
from psycopg import sql
def main():
    p=argparse.ArgumentParser(); p.add_argument('--host',default='127.0.0.1'); p.add_argument('--port',type=int,default=5432); p.add_argument('--database',default='coal_network'); p.add_argument('--user',default='coal_network_writer'); p.add_argument('--password-env',default='COAL_PG_WRITER_PASSWORD'); p.add_argument('--schema',default='coal_network'); a=p.parse_args(); password=os.environ.get(a.password_env)
    if not password: raise ValueError('missing environment variable: '+a.password_env)
    with psycopg.connect(host=a.host,port=a.port,dbname=a.database,user=a.user,password=password,sslmode='prefer') as conn:
        conn.execute(sql.SQL('grant select on all tables in schema {} to {}').format(sql.Identifier(a.schema),sql.Identifier('coal_network_readonly'))); conn.commit()
    print('Read-only grants refreshed')
if __name__=='__main__': main()
