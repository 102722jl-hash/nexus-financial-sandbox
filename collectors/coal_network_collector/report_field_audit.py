"""Read-only audit of candidate fields in downloaded company reports."""
import json,re,sqlite3
from pathlib import Path
from pypdf import PdfReader
ROOT=Path(__file__).parent
TERMS=['燃料成本','燃煤成本','标煤单价','入炉标煤单价','供电煤耗','发电煤耗','厂用电率','利用小时','资本性支出','资本开支','购建固定资产','折旧','货币资金','短期借款','长期借款','应付债券','有息负债','净债务','火电装机','煤电装机','控股装机','发电量','上网电量','上网电价']
def audit():
    db=sqlite3.connect(ROOT/'coal_network.db'); rows=db.execute("select document_id,source_name,snapshot_path from raw_documents where document_id like 'company_%' and snapshot_path is not null order by source_name,document_id").fetchall(); result=[]
    for doc,name,path in rows:
        pages=PdfReader(path).pages; found={}
        for page_no,page in enumerate(pages,1):
            text=re.sub(r'\s+',' ',page.extract_text() or '')
            for term in TERMS:
                if term in text:
                    matches=[]
                    for m in list(re.finditer(re.escape(term),text))[:3]: matches.append(text[max(0,m.start()-80):min(len(text),m.end()+140)])
                    found.setdefault(term,[]).append({'page':page_no,'contexts':matches})
        result.append({'document_id':doc,'company':name,'path':path,'pages':len(pages),'found':found})
    db.close(); (ROOT/'report_field_audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8'); return result
if __name__=='__main__':
    data=audit(); print(json.dumps([{'document_id':x['document_id'],'company':x['company'],'pages':x['pages'],'terms':{k:[p['page'] for p in v] for k,v in x['found'].items()}} for x in data],ensure_ascii=False,indent=2))
