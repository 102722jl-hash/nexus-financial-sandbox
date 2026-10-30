"""Official GFEX daily market proxy for lithium carbonate."""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import urllib.parse
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests

from ingest_v1 import ingest_record
from initialize import DEFAULT_DB, ROOT, initialize


API_URL = "http://www.gfex.com.cn/u/interfacesWebTiDayQuotes/loadList"
PAGE_URL = "http://www.gfex.com.cn/gfex/rihq/hqsj_tjsj.shtml"
SNAPSHOT_DIR = ROOT / "snapshots" / "gfex_market"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def fetch_day(day: date) -> tuple[bytes, list[dict]]:
    body = urllib.parse.urlencode({
        "trade_date": day.strftime("%Y%m%d"), "trade_type": "0", "variety": "lc",
    }).encode("ascii")
    response = requests.post(
        API_URL, data=body,
        headers={"User-Agent": "Mozilla/5.0", "Referer": PAGE_URL, "Content-Type": "application/x-www-form-urlencoded"},
        timeout=45,
    )
    response.raise_for_status()
    raw = response.content
    payload = json.loads(raw.decode("utf-8", "replace"))
    rows = [
        item for item in payload.get("data") or []
        if str(item.get("varietyOrder") or "").lower() == "lc"
        and item.get("close") is not None and float(item.get("volumn") or 0) > 0
    ]
    return raw, rows


def store_snapshot(db_path: Path, day: date, raw: bytes) -> tuple[str, str, str]:
    digest = hashlib.sha256(raw).hexdigest()
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    path = SNAPSHOT_DIR / f"{day.isoformat()}-{digest}.json"
    if not path.exists():
        path.write_bytes(raw)
    document_id = f"raw::gfex::{day.isoformat()}::{digest}"
    conn = sqlite3.connect(db_path)
    with conn:
        conn.execute(
            """INSERT OR IGNORE INTO raw_documents
               (document_id,source_url,source_name,retrieved_at,content_type,http_status,
                content_sha256,snapshot_path,parse_status,error_message)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (document_id, API_URL, "广期所碳酸锂日行情", utc_now(), "application/json", 200,
             digest, str(path), "PARSED", None),
        )
    conn.close()
    return str(path), digest, document_id


def collect(db_path: Path = DEFAULT_DB, days: int = 14, max_accepts: int = 1) -> dict:
    initialize(db_path)
    accepted = []
    no_data = []
    errors = []
    # The scheduled task runs before the exchange closes, so always start at
    # yesterday and stop after the latest completed trading day is found.
    for offset in range(1, max(2, days + 1)):
        day = date.today() - timedelta(days=offset)
        try:
            raw, rows = fetch_day(day)
        except Exception as exc:
            errors.append({"date": day.isoformat(), "error": f"{type(exc).__name__}: {exc}"})
            continue
        if not rows:
            no_data.append(day.isoformat())
            continue
        # The most liquid listed contract is the explicit daily market proxy.
        row = max(rows, key=lambda item: float(item.get("volumn") or 0))
        snapshot_path, digest, document_id = store_snapshot(db_path, day, raw)
        quote = json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        evidence_id = "evidence::gfex::" + hashlib.sha256(
            f"{day.isoformat()}|{row.get('delivMonth')}|{quote}".encode("utf-8")
        ).hexdigest()
        result = ingest_record(db_path, {
            "evidence": {
                "evidence_id": evidence_id,
                "source_type": "MARKET_PROXY",
                "source_name": "广期所碳酸锂期货日行情",
                "publisher": "广州期货交易所",
                "published_at": f"{day.isoformat()}T15:00:00+08:00",
                "retrieved_at": utc_now(),
                "original_quote": quote,
                "locator": f"JSON row; varietyOrder=lc; delivMonth={row.get('delivMonth')}; field=close; selection=max(volumn)",
                "source_url": API_URL,
                "anchor_at": utc_now(),
                "source_tier": "T1",
                "snapshot_path": snapshot_path,
                "snapshot_sha256": digest,
            },
            "metric": {
                "metric_value_id": "metric::gfex::" + hashlib.sha256(
                    f"LITHIUM_CARBONATE_PRICE|{day.isoformat()}".encode("utf-8")
                ).hexdigest(),
                "metric_code": "LITHIUM_CARBONATE_PRICE",
                "entity_code": None,
                "value": row["close"],
                "unit": "元/吨",
                "currency": "CNY",
                "as_of_date": day.isoformat(),
                "source_table": "gfex_daily_futures_proxy",
                "source_row_key": f"lc|{day.isoformat()}|{row.get('delivMonth')}|most_liquid",
            },
        }, initialize_db=False)
        accepted.append({**result, "contract": f"LC{row.get('delivMonth')}", "volume": row.get("volumn")})
        if len(accepted) >= max(1, max_accepts):
            break
    return {
        "status": "OK" if accepted else "ERROR",
        "accepted_rows": len(accepted), "accepted": accepted,
        "no_data_dates": no_data, "errors": errors,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--days", type=int, default=14)
    parser.add_argument("--max-accepts", type=int, default=1)
    args = parser.parse_args()
    print(json.dumps(collect(args.db, args.days, args.max_accepts), ensure_ascii=False, indent=2))
