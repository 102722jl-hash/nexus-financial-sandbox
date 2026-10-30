"""Discover and snapshot relevant company disclosures from CNINFO."""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

from contract_v1 import COMPANIES, NETWORK_ID
from initialize import DEFAULT_DB, ROOT, initialize

ENDPOINT = "https://www.cninfo.com.cn/new/hisAnnouncement/query"
ORGS = {
    "002594.SZ": "gssz0002594",
    "601127.SH": "gssh0601127",
    "600733.SH": "gssh0600733",
    "000625.SZ": "gssz0000625",
    "601633.SH": "gssh0601633",
}
KEYWORDS = (
    "产销快报", "产、销快报", "月份产销", "年度报告", "半年度报告",
    "第一季度报告", "第三季度报告", "季度报告",
)
SNAPSHOT_DIR = ROOT / "snapshots" / "company_announcements"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def request_page(code: str, page: int = 1, page_size: int = 30) -> dict:
    symbol = code[:6]
    is_sz = code.endswith(".SZ")
    form = {
        "pageNum": str(page),
        "pageSize": str(page_size),
        "column": "szse" if is_sz else "sse",
        "tabName": "fulltext",
        "plate": "sz" if is_sz else "sh",
        "stock": f"{symbol},{ORGS[code]}",
        "searchkey": "",
        "secid": "",
        "category": "",
        "trade": "",
        "seDate": "",
        "sortName": "",
        "sortType": "",
        "isHLtitle": "true",
    }
    headers = {
            "User-Agent": "Mozilla/5.0 new-energy-vehicle-collector/1.0",
            "Referer": "https://www.cninfo.com.cn/",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    }
    def post(values: dict) -> dict:
        request = urllib.request.Request(
            ENDPOINT, data=urllib.parse.urlencode(values).encode("utf-8"), headers=headers
        )
        with urllib.request.urlopen(request, timeout=45) as response:
            return json.loads(response.read().decode("utf-8"))
    payload = post(form)
    if payload.get("announcements"):
        return payload
    # Some issuers no longer accept the legacy org-id mapping. Fall back to
    # full-text company-name search, then normalize() filters the security code.
    form["stock"] = ""
    form["searchkey"] = COMPANIES[code]
    return post(form)


def normalize(code: str, payload: dict) -> list[dict]:
    results = []
    for item in payload.get("announcements") or []:
        if item.get("secCode") and item.get("secCode") != code[:6]:
            continue
        title = (item.get("announcementTitle") or "").replace("<em>", "").replace("</em>", "")
        if not any(keyword in title for keyword in KEYWORDS):
            continue
        adjunct = item.get("adjunctUrl") or ""
        if not adjunct.lower().endswith(".pdf"):
            continue
        remote_id = str(item.get("announcementId") or adjunct)
        results.append({
            "announcement_id": f"{code}:{remote_id}",
            "entity_code": code,
            "title": title,
            "published_ms": item.get("announcementTime"),
            "pdf_url": "https://static.cninfo.com.cn/" + adjunct.lstrip("/"),
        })
    return results


def discover(db_path: Path, code: str, max_pages: int = 3) -> list[dict]:
    initialize(db_path)
    conn = sqlite3.connect(db_path)
    run_id = f"discovery::{code}::{uuid.uuid4().hex}"
    try:
        by_id = {}
        for page in range(1, max_pages + 1):
            page_items = normalize(code, request_page(code, page=page))
            for item in page_items:
                by_id[item["announcement_id"]] = item
        items = list(by_id.values())
        with conn:
            conn.execute(
                "INSERT INTO discovery_runs VALUES (?,?,?,?,?,?,?)",
                (run_id, ENDPOINT, code, utc_now(), len(items), "SUCCESS", None),
            )
            for item in items:
                conn.execute(
                    """INSERT INTO announcement_catalogue
                       (announcement_id,network_id,entity_code,title,published_ms,pdf_url,
                        discovered_at,document_id,status,error_message)
                       VALUES (?,?,?,?,?,?,?,?,?,?)
                       ON CONFLICT(announcement_id) DO UPDATE SET
                         title=excluded.title,published_ms=excluded.published_ms,
                         pdf_url=excluded.pdf_url""",
                    (item["announcement_id"], NETWORK_ID, code, item["title"],
                     item["published_ms"], item["pdf_url"], utc_now(), None, "DISCOVERED", None),
                )
        return items
    except Exception as exc:
        with conn:
            conn.execute(
                "INSERT INTO discovery_runs VALUES (?,?,?,?,?,?,?)",
                (run_id, ENDPOINT, code, utc_now(), None, "ERROR", f"{type(exc).__name__}: {exc}"),
            )
        raise
    finally:
        conn.close()


def _download(url: str) -> tuple[bytes, str, int]:
    request = urllib.request.Request(
        url, headers={"User-Agent": "Mozilla/5.0 new-energy-vehicle-collector/1.0"}
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read(), response.headers.get("Content-Type", ""), response.status


def download_pending(db_path: Path) -> dict:
    initialize(db_path)
    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        """SELECT announcement_id,entity_code,pdf_url
           FROM announcement_catalogue WHERE network_id=? AND status IN ('DISCOVERED','ERROR')""",
        (NETWORK_ID,),
    ).fetchall()
    downloaded = 0
    errors = []
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    for announcement_id, code, url in rows:
        try:
            body, content_type, status = _download(url)
            if not body.startswith(b"%PDF"):
                raise ValueError("DOWNLOADED_CONTENT_IS_NOT_PDF")
            digest = hashlib.sha256(body).hexdigest()
            path = SNAPSHOT_DIR / f"{digest}.pdf"
            if not path.exists():
                path.write_bytes(body)
            document_id = f"raw::cninfo::{digest}"
            with conn:
                conn.execute(
                    """INSERT OR IGNORE INTO raw_documents
                       (document_id,source_url,source_name,retrieved_at,content_type,http_status,
                        content_sha256,snapshot_path,parse_status,error_message)
                       VALUES (?,?,?,?,?,?,?,?,?,?)""",
                    (document_id, url, COMPANIES[code], utc_now(), content_type, status,
                     digest, str(path), "DOWNLOADED", None),
                )
                conn.execute(
                    """UPDATE announcement_catalogue
                       SET document_id=?,status='DOWNLOADED',error_message=NULL
                       WHERE announcement_id=?""",
                    (document_id, announcement_id),
                )
            downloaded += 1
        except Exception as exc:
            message = f"{type(exc).__name__}: {exc}"
            errors.append({"announcement_id": announcement_id, "error": message})
            with conn:
                conn.execute(
                    "UPDATE announcement_catalogue SET status='ERROR',error_message=? WHERE announcement_id=?",
                    (message, announcement_id),
                )
    conn.close()
    return {"pending": len(rows), "downloaded": downloaded, "errors": errors}


def collect(db_path: Path = DEFAULT_DB, download: bool = True) -> dict:
    discovered = {}
    errors = {}
    for code in COMPANIES:
        try:
            discovered[code] = len(discover(db_path, code))
        except Exception as exc:
            errors[code] = f"{type(exc).__name__}: {exc}"
    result = {"discovered": discovered, "discovery_errors": errors}
    if download:
        result["download"] = download_pending(db_path)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--no-download", action="store_true")
    args = parser.parse_args()
    print(json.dumps(collect(args.db, not args.no_download), ensure_ascii=False, indent=2))
