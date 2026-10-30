"""T3 Sina daily-price adapter; values are stored only as MARKET_PROXY."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from contract_v1 import COMPANIES
from ingest_v1 import ingest_record
from initialize import DEFAULT_DB, ROOT, initialize

BASE = "https://quotes.sina.cn/cn/api/jsonp_v2.php/var%20_data=/CN_MarketData.getKLineData"
SNAPSHOT_DIR = ROOT / "snapshots" / "sina_market"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sina_symbol(code: str) -> str:
    return ("sz" if code.endswith(".SZ") else "sh") + code[:6]


def fetch(code: str, datalen: int = 400) -> tuple[str, bytes, list[dict]]:
    url = f"{BASE}?symbol={sina_symbol(code)}&scale=240&ma=no&datalen={datalen}"
    request = urllib.request.Request(
        url, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://finance.sina.com.cn/"}
    )
    with urllib.request.urlopen(request, timeout=45) as response:
        raw = response.read()
    text = raw.decode("utf-8", "ignore")
    match = re.search(r"var\s+_data=\((\[.*\])\);?", text, re.S)
    if not match:
        raise ValueError("SINA_RESPONSE_FORMAT_NOT_RECOGNIZED")
    return url, raw, json.loads(match.group(1))


def store_snapshot(db_path: Path, url: str, raw: bytes) -> tuple[str, str]:
    digest = hashlib.sha256(raw).hexdigest()
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    path = SNAPSHOT_DIR / f"{digest}.txt"
    if not path.exists():
        path.write_bytes(raw)
    document_id = f"raw::sina::{digest}"
    conn = sqlite3.connect(db_path)
    with conn:
        conn.execute(
            """INSERT OR IGNORE INTO raw_documents
               (document_id,source_url,source_name,retrieved_at,content_type,http_status,
                content_sha256,snapshot_path,parse_status,error_message)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (document_id, url, "新浪财经日线接口", utc_now(), "text/javascript", 200,
             digest, str(path), "PARSED", None),
        )
    conn.close()
    return str(path), digest


def collect(db_path: Path = DEFAULT_DB, datalen: int = 400) -> list[dict]:
    initialize(db_path)
    results = []
    for code, company_name in COMPANIES.items():
        try:
            url, raw, items = fetch(code, datalen)
            snapshot_path, digest = store_snapshot(db_path, url, raw)
            accepted = 0
            for item in items:
                day = item.get("day")
                close = item.get("close")
                if not day or close in (None, ""):
                    continue
                quote = json.dumps(item, ensure_ascii=False, sort_keys=True)
                evidence_id = "evidence::sina::" + hashlib.sha256(
                    f"{code}|{day}|{url}|{quote}".encode("utf-8")
                ).hexdigest()
                metric_value_id = "metric::sina::" + hashlib.sha256(
                    f"{code}|{day}".encode("utf-8")
                ).hexdigest()
                payload = {
                    "evidence": {
                        "evidence_id": evidence_id,
                        "source_type": "MARKET_PROXY",
                        "source_name": "新浪财经日线行情",
                        "publisher": "新浪财经",
                        "published_at": f"{day}T15:00:00+08:00",
                        "retrieved_at": utc_now(),
                        "original_quote": quote,
                        "locator": f"JSON row where day={day}; field=close",
                        "source_url": url,
                        "anchor_at": utc_now(),
                        "declared_role": "POST_EVENT_VALIDATION",
                        "source_tier": "T3",
                        "snapshot_path": snapshot_path,
                        "snapshot_sha256": digest,
                    },
                    "metric": {
                        "metric_value_id": metric_value_id,
                        "metric_code": "CLOSE_PRICE",
                        "entity_code": code,
                        "value": close,
                        "unit": "元/股",
                        "currency": "CNY",
                        "as_of_date": day,
                        "source_table": "sina_daily_kline",
                        "source_row_key": f"{code}|{day}",
                    },
                }
                result = ingest_record(db_path, payload, initialize_db=False)
                accepted += result["status"] == "ACCEPTED"
            results.append({
                "entity_code": code,
                "company": company_name,
                "status": "OK",
                "accepted_rows": accepted,
                "latest": items[-1] if items else None,
                "source_tier": "T3",
                "value_status": "MARKET_PROXY",
            })
        except Exception as exc:
            results.append({
                "entity_code": code, "company": company_name,
                "status": "ERROR", "error": f"{type(exc).__name__}: {exc}",
            })
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--datalen", type=int, default=400)
    args = parser.parse_args()
    print(json.dumps(collect(args.db, args.datalen), ensure_ascii=False, indent=2))
