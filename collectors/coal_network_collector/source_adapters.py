"""Coal/power public-source adapters.

Adapters only acquire public pages and return raw snapshots. Domain-specific
field extraction should be added per source after inspecting the snapshot.
"""
from __future__ import annotations
import hashlib, json, sqlite3, urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent
SOURCES = {
    "stats_energy": ("国家统计局能源生产", "https://www.stats.gov.cn/sj/zxfb/", "T1"),
    "nea_power": ("国家能源局电力统计", "https://www.nea.gov.cn/", "T1"),
    "ncexc_coal": ("全国煤炭交易中心", "https://www.ncexc.cn/", "T1"),
    "sse_announcements": ("上海证券交易所公告", "https://www.sse.com.cn/disclosure/listedinfo/", "T2"),
    "cninfo_announcements": ("巨潮资讯公告", "https://www.cninfo.com.cn/", "T2"),
}

def utc_now():
    return datetime.now(timezone.utc).isoformat()

def acquire(db: sqlite3.Connection, source_id: str, url: str | None = None) -> dict:
    if source_id not in SOURCES:
        raise ValueError(f"unknown source: {source_id}")
    name, default_url, _tier = SOURCES[source_id]
    target = url or default_url
    req = urllib.request.Request(target, headers={"User-Agent": "coal-network-collector/0.1"})
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            body = response.read(); status = response.status
            content_type = response.headers.get("Content-Type", "")
        digest = hashlib.sha256(body).hexdigest()
        snapshot_dir = ROOT / "raw"; snapshot_dir.mkdir(exist_ok=True)
        path = snapshot_dir / f"{digest}.bin"; path.write_bytes(body)
        doc_id = f"{source_id}:{digest[:20]}"
        db.execute("INSERT OR IGNORE INTO raw_documents VALUES(?,?,?,?,?,?,?,?,?,?)",
                   (doc_id, target, name, utc_now(), content_type, status, digest,
                    str(path), "DOWNLOADED", None))
        db.commit()
        return {"document_id": doc_id, "source_id": source_id, "url": target,
                "sha256": digest, "path": str(path), "status": "DOWNLOADED"}
    except Exception as exc:
        return {"source_id": source_id, "url": target, "status": "ERROR", "error": str(exc)}

def acquire_all(db: sqlite3.Connection) -> list[dict]:
    return [acquire(db, source_id) for source_id in SOURCES]

def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=str(ROOT / "coal_network.db"))
    parser.add_argument("--source", choices=[*SOURCES, "all"], default="all")
    args = parser.parse_args()
    db = sqlite3.connect(args.db)
    results = acquire_all(db) if args.source == "all" else [acquire(db, args.source)]
    print(json.dumps(results, ensure_ascii=False, indent=2))
    db.close()

if __name__ == "__main__":
    main()
