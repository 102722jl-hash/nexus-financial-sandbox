"""Public association adapter for NEV passenger-vehicle wholesale indicators."""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sqlite3
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from ingest_v1 import ingest_record
from initialize import DEFAULT_DB, ROOT, initialize


LIST_URL = "https://www.cada.cn/Trends/list_91_1.html"
SNAPSHOT_DIR = ROOT / "snapshots" / "cada_industry"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def fetch(url: str) -> tuple[bytes, str]:
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=45) as response:
        raw = response.read()
        final_url = response.geturl()
    return raw, final_url


def plain_text(raw: bytes) -> str:
    text = raw.decode("utf-8", "replace")
    text = re.sub(r"<script\b[^>]*>.*?</script>|<style\b[^>]*>.*?</style>", " ", text, flags=re.I | re.S)
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", text)).split())


def discover_latest() -> str:
    raw, final_url = fetch(LIST_URL)
    source = raw.decode("utf-8", "replace")
    candidates = []
    for href, label in re.findall(r"href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>", source, re.I | re.S):
        title = " ".join(html.unescape(re.sub(r"<[^>]+>", " ", label)).split())
        if "月份全国乘用车市场分析" not in title:
            continue
        match = re.search(r"info_91_(\d+)\.html", href)
        if match:
            candidates.append((int(match.group(1)), urllib.parse.urljoin(final_url, href)))
    if not candidates:
        raise ValueError("CADA_MONTHLY_REPORT_NOT_FOUND")
    return max(candidates)[1]


def parse_report(text: str) -> dict:
    title = re.search(r"(20\d{2})年(\d{1,2})月份全国乘用车市场分析", text)
    if not title:
        raise ValueError("CADA_REPORT_PERIOD_NOT_FOUND")
    year, month = int(title.group(1)), int(title.group(2))
    sales = re.search(
        rf"{month}月新能源乘用车(?:厂商)?批发(?:销量)?达到\s*([0-9]+(?:\.[0-9]+)?)\s*万辆",
        text,
    )
    penetration = re.search(
        rf"{month}月新能源车厂商批发渗透率\s*([0-9]+(?:\.[0-9]+)?)%",
        text,
    )
    published = re.search(r"时间[:：]\s*(20\d{2}-\d{2}-\d{2})\s*(\d{2}:\d{2}:\d{2})", text)
    if not sales or not penetration or not published:
        raise ValueError("CADA_REQUIRED_FIELDS_NOT_FOUND")
    return {
        "period": f"{year:04d}-{month:02d}",
        "published_at": f"{published.group(1)}T{published.group(2)}+08:00",
        "sales": float(sales.group(1)) * 10_000,
        "sales_quote": sales.group(0),
        "penetration": float(penetration.group(1)),
        "penetration_quote": penetration.group(0),
    }


def store_snapshot(db_path: Path, url: str, raw: bytes) -> tuple[str, str, str]:
    digest = hashlib.sha256(raw).hexdigest()
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    path = SNAPSHOT_DIR / f"{digest}.html"
    if not path.exists():
        path.write_bytes(raw)
    document_id = f"raw::cada::{digest}"
    conn = sqlite3.connect(db_path)
    with conn:
        conn.execute(
            """INSERT OR IGNORE INTO raw_documents
               (document_id,source_url,source_name,retrieved_at,content_type,http_status,
                content_sha256,snapshot_path,parse_status,error_message)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (document_id, url, "全国乘用车市场月度分析", utc_now(), "text/html", 200,
             digest, str(path), "PARSED", None),
        )
    conn.close()
    return str(path), digest, document_id


def collect(db_path: Path = DEFAULT_DB) -> dict:
    initialize(db_path)
    url = discover_latest()
    raw, url = fetch(url)
    text = plain_text(raw)
    parsed = parse_report(text)
    snapshot_path, digest, document_id = store_snapshot(db_path, url, raw)
    specs = [
        ("NEV_INDUSTRY_SALES", parsed["sales"], "辆", parsed["sales_quote"], "wholesale-sales"),
        ("NEV_PENETRATION_RATE", parsed["penetration"], "%", parsed["penetration_quote"], "wholesale-penetration"),
    ]
    accepted = []
    for code, value, unit, quote, field in specs:
        evidence_key = f"{document_id}|{code}|{parsed['period']}|{quote}"
        evidence_id = "evidence::cada::" + hashlib.sha256(evidence_key.encode("utf-8")).hexdigest()
        result = ingest_record(db_path, {
            "evidence": {
                "evidence_id": evidence_id,
                "source_type": "SOURCE_FACT",
                "source_name": "全国乘用车市场月度分析",
                "publisher": "中国汽车流通协会乘用车市场信息联席分会",
                "published_at": parsed["published_at"],
                "retrieved_at": utc_now(),
                "original_quote": quote,
                "locator": f"article:{parsed['period']};field:{field}",
                "source_url": url,
                "anchor_at": utc_now(),
                "source_tier": "T2",
                "snapshot_path": snapshot_path,
                "snapshot_sha256": digest,
            },
            "metric": {
                "metric_value_id": "metric::cada::" + hashlib.sha256(
                    f"{code}|{parsed['period']}".encode("utf-8")
                ).hexdigest(),
                "metric_code": code,
                "entity_code": None,
                "value": value,
                "unit": unit,
                "report_period": parsed["period"],
                "source_table": "cada_monthly_passenger_vehicle_report",
                "source_row_key": f"{parsed['period']}|{field}",
            },
        }, initialize_db=False)
        accepted.append(result)
    return {"status": "OK", "source_url": url, "period": parsed["period"], "accepted": accepted}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    args = parser.parse_args()
    print(json.dumps(collect(args.db), ensure_ascii=False, indent=2))
