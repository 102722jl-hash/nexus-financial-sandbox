import json, sqlite3
from pathlib import Path

db=sqlite3.connect(Path(__file__).parent/'coal_network.db')
tables=['network_registry','network_layers','entities','raw_documents','evidence','metric_values','review_queue']
result={name:db.execute(f'SELECT COUNT(*) FROM {name}').fetchone()[0] for name in tables}
result['raw_status']={row[0]:row[1] for row in db.execute('SELECT parse_status,COUNT(*) FROM raw_documents GROUP BY parse_status')}
print(json.dumps(result,ensure_ascii=False,indent=2))
db.close()
