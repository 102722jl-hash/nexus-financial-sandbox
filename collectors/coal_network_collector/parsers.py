"""Deterministic parsers for coal and power public-source snapshots."""
from __future__ import annotations
import html, re
from dataclasses import dataclass
from datetime import datetime, timezone

@dataclass(frozen=True)
class Fact:
    metric_code: str
    value: float
    unit: str
    report_period: str | None
    original_quote: str
    locator: str

def clean_html(raw: bytes) -> str:
    text = raw.decode("utf-8", errors="ignore")
    text = re.sub(r"(?is)<script.*?</script>|<style.*?</style>", " ", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()

def publication_date(text: str) -> str | None:
    m = re.search(r"(20\d{2})[年\-/\.](\d{1,2})[月\-/\.](\d{1,2})日?", text)
    return f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}" if m else None

def report_period(text: str) -> str | None:
    m = re.search(r"(20\d{2})年\s*(\d{1,2})月份?", text)
    if m: return f"{m.group(1)}-{int(m.group(2)):02d}"
    m = re.search(r"(20\d{2})年\s*1[—-](\d{1,2})月份?", text)
    return f"{m.group(1)}-01/{m.group(1)}-{int(m.group(2)):02d}" if m else None

def _number(value: str) -> float:
    return float(value.replace(",", ""))

def _facts(text: str, specs: list[tuple[str,str,str]]) -> list[Fact]:
    period = report_period(text); out=[]
    for code, label, unit in specs:
        pattern=rf"{label}[^。；;]{{0,45}}?([0-9][0-9,]*(?:\.[0-9]+)?)\s*{re.escape(unit)}"
        for i,m in enumerate(re.finditer(pattern,text)):
            quote=m.group(0).strip(); out.append(Fact(code,_number(m.group(1)),unit,period,quote,f"text:{label}:{i+1}"))
    return out

def parse_stats_energy(raw: bytes) -> list[Fact]:
    text=clean_html(raw)
    return _facts(text,[('RAW_COAL_OUTPUT','原煤产量','万吨'),('POWER_GENERATION','火力发电量','亿千瓦时')])

def parse_nea_power(raw: bytes) -> list[Fact]:
    text=clean_html(raw)
    return _facts(text,[('UTILIZATION_HOURS_THERMAL','火电','小时'),('POWER_CONSUMPTION','全社会用电量','亿千瓦时'),('THERMAL_CAPACITY','火电','万千瓦')])

def parse_ncexc_coal(raw: bytes) -> list[Fact]:
    text=clean_html(raw); period=publication_date(text); out=[]
    patterns=[
      ('COAL_PRICE_5500',r'(?:动力煤[^。；]{0,30}?5500K?|5500K[^。；]{0,30}?)([0-9][0-9,]*(?:\.[0-9]+)?)\s*元/?吨'),
      ('COAL_PRICE_5000',r'(?:动力煤[^。；]{0,30}?5000K?|5000K[^。；]{0,30}?)([0-9][0-9,]*(?:\.[0-9]+)?)\s*元/?吨')]
    for code,pattern in patterns:
        for i,m in enumerate(re.finditer(pattern,text)):
            out.append(Fact(code,_number(m.group(1)),'元/吨',period,m.group(0),f'text:{code}:{i+1}'))
    return out

PARSERS={'stats_energy':parse_stats_energy,'nea_power':parse_nea_power,'ncexc_coal':parse_ncexc_coal}
