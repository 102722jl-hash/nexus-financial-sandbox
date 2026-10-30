"""Deterministic extraction of common financial statement fields from PDF text."""
from __future__ import annotations
import re

SPECS=[
 ('REVENUE','营业收入','元'),('OPERATING_COST','营业成本','元'),
 ('NET_PROFIT','归属于上市公司股东的净利润','元'),
 ('OPERATING_CASH_FLOW','经营活动产生的现金流量净额','元'),
 ('TOTAL_ASSETS','资产总额','元'),('TOTAL_LIABILITIES','负债合计','元')]

def parse_financial_metrics(text):
    out=[]
    for code,label,unit in SPECS:
        pattern=rf'{label}\s*[:：]?\s*([+-]?[0-9][0-9,]*(?:\.[0-9]+)?)'
        for i,m in enumerate(re.finditer(pattern,text)):
            out.append({'metric_code':code,'value':float(m.group(1).replace(',','')),
              'unit':unit,'quote':m.group(0),'locator':f'financial:{label}:{i+1}'})
    return out

def detect_currency_scale(text):
    m=re.search(r'(?:单位|金额单位)\s*[:：]\s*(人民币)?\s*(元|万元|百万元|亿元)',text)
    return m.group(2) if m else None

def scale_to_yuan(value,scale):
    return value*{'元':1,'万元':10000,'百万元':1000000,'亿元':100000000}[scale]
