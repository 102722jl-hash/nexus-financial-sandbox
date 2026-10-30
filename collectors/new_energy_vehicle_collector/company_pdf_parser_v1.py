"""Rule-based parser for monthly NEV production and sales disclosures."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from pypdf import PdfReader

from contract_v1 import COMPANIES, NETWORK_ID
from ingest_v1 import IngestRejected, ingest_record
from initialize import DEFAULT_DB, initialize


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def pdf_text(body: bytes) -> str:
    pages = []
    for number, page in enumerate(PdfReader(io.BytesIO(body)).pages, 1):
        pages.append(f"\n[[PAGE:{number}]]\n{page.extract_text() or ''}")
    return "".join(pages)


def report_period(title: str, text: str) -> str | None:
    match = re.search(r"(20\d{2})\s*年\s*(\d{1,2})\s*月", title + "\n" + text[:600])
    return f"{int(match.group(1)):04d}-{int(match.group(2)):02d}" if match else None


def published_date(text: str) -> str | None:
    matches = re.findall(r"(20\d{2})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日", text)
    if not matches:
        return None
    year, month, day = matches[-1]
    return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"


def page_at(text: str, position: int) -> str:
    pages = re.findall(r"\[\[PAGE:(\d+)\]\]", text[:position])
    return pages[-1] if pages else "unknown"


def _metric(code: str, value: str, quote: str, page: str) -> dict:
    return {
        "metric_code": code,
        "value": float(value.replace(",", "")),
        "unit": "辆",
        "quote": " ".join(quote.split()),
        "locator": f"page:{page};table:monthly-production-sales;metric:{code}",
    }


def is_monthly_disclosure(title: str) -> bool:
    return "产销" in title or "产、销" in title


def parse_monthly_metrics(entity_code: str, text: str) -> list[dict]:
    metrics = []
    if entity_code == "002594.SZ":
        pattern = (
            r"新能源汽车\s+([\d,]+)\s+[\d,]+\s+[\d,]+\s+[\d,]+\s+[-\d.]+%"
            r"\s+([\d,]+)\s+[\d,]+\s+[\d,]+\s+[\d,]+\s+[-\d.]+%"
        )
        match = re.search(pattern, text)
        if match:
            page = page_at(text, match.start())
            metrics.extend([
                _metric("COMPANY_NEV_PRODUCTION", match.group(1), match.group(0), page),
                _metric("COMPANY_NEV_SALES", match.group(2), match.group(0), page),
            ])
        export = re.search(r"出口新能源汽车合计\s*([\d,]+)\s*辆", text)
        if export:
            metrics.append(_metric(
                "COMPANY_NEV_EXPORTS", export.group(1), export.group(0),
                page_at(text, export.start()),
            ))
    elif entity_code == "601127.SH":
        pattern = (
            r"新能源汽车\s+([\d,]+)\s+[-\d.]+%\s+[\d,]+\s+[-\d.]+%"
            r"\s+([\d,]+)\s+[-\d.]+%\s+[\d,]+\s+[-\d.]+%"
        )
        match = re.search(pattern, text)
        if match:
            page = page_at(text, match.start())
            metrics.extend([
                _metric("COMPANY_NEV_PRODUCTION", match.group(1), match.group(0), page),
                _metric("COMPANY_NEV_SALES", match.group(2), match.group(0), page),
            ])
    elif entity_code == "600733.SH":
        pattern = (
            r"北京新能源汽车\s*股份有限公司\s+([\d,]+)\s+[\d,]+\s+[-\d.]+%"
            r"\s+[\d,]+\s+[\d,]+\s+[-\d.]+%\s+([\d,]+)"
        )
        match = re.search(pattern, text)
        if match:
            page = page_at(text, match.start())
            metrics.extend([
                _metric("COMPANY_NEV_PRODUCTION", match.group(1), match.group(0), page),
                _metric("COMPANY_NEV_SALES", match.group(2), match.group(0), page),
            ])
    elif entity_code == "000625.SZ":
        pattern = (
            r"新能源汽车\s+([\d,]+)\s+[\d,]+\s+[-\d.]+%"
            r"\s+[\d,]+\s+[\d,]+\s+[-\d.]+%\s+([\d,]+)"
        )
        match = re.search(pattern, text)
        if match:
            page = page_at(text, match.start())
            metrics.extend([
                _metric("COMPANY_NEV_PRODUCTION", match.group(1), match.group(0), page),
                _metric("COMPANY_NEV_SALES", match.group(2), match.group(0), page),
            ])
    elif entity_code == "601633.SH":
        match = re.search(
            r"\d{1,2}\s*月新能源(?:汽车|车)销售\s*([\d,]+)\s*台",
            text,
        )
        if match:
            metrics.append(_metric(
                "COMPANY_NEV_SALES", match.group(1), match.group(0),
                page_at(text, match.start()),
            ))
    return metrics


def import_pending(db_path: Path = DEFAULT_DB) -> dict:
    initialize(db_path)
    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        """SELECT a.announcement_id,a.entity_code,a.title,a.pdf_url,a.document_id,
                  r.retrieved_at,r.content_sha256,r.snapshot_path
           FROM announcement_catalogue a
           JOIN raw_documents r ON r.document_id=a.document_id
           WHERE a.network_id=? AND (
             a.status='DOWNLOADED' OR (
               a.status='NEEDS_REVIEW' AND (a.title LIKE '%产销%' OR a.title LIKE '%产、销%')
             )
           )""",
        (NETWORK_ID,),
    ).fetchall()
    imported_documents = 0
    imported_values = 0
    needs_review = 0
    errors = []
    for announcement_id, entity_code, title, url, document_id, retrieved, sha, path in rows:
        try:
            text = pdf_text(Path(path).read_bytes())
            period = report_period(title, text)
            published = published_date(text)
            monthly_disclosure = is_monthly_disclosure(title)
            metrics = parse_monthly_metrics(entity_code, text) if monthly_disclosure else []
            if not period or not published or not metrics:
                reasons = []
                if not monthly_disclosure:
                    reasons.append("FINANCIAL_REPORT_PARSER_NOT_YET_ENABLED")
                if not period:
                    reasons.append("REPORT_PERIOD_MISSING")
                if not published:
                    reasons.append("PUBLISHED_AT_MISSING")
                if monthly_disclosure and not metrics:
                    reasons.append("MONTHLY_TABLE_NOT_PARSED")
                with conn:
                    conn.execute(
                        """INSERT INTO quarantine(object_type,object_id,reason_code,payload_json,created_at,status)
                           VALUES (?,?,?,?,?,?)""",
                        ("COMPANY_PDF", document_id, ",".join(reasons),
                         json.dumps({"title": title, "url": url}, ensure_ascii=False),
                         utc_now(), "OPEN"),
                    )
                    conn.execute(
                        "UPDATE raw_documents SET parse_status='NEEDS_REVIEW' WHERE document_id=?",
                        (document_id,),
                    )
                    conn.execute(
                        "UPDATE announcement_catalogue SET status='NEEDS_REVIEW' WHERE announcement_id=?",
                        (announcement_id,),
                    )
                needs_review += 1
                continue
            accepted = 0
            for item in metrics:
                evidence_key = f"{document_id}|{item['metric_code']}|{item['locator']}|{item['quote']}"
                evidence_id = "evidence::cninfo::" + hashlib.sha256(evidence_key.encode("utf-8")).hexdigest()
                payload = {
                    "evidence": {
                        "evidence_id": evidence_id,
                        "source_type": "SOURCE_FACT",
                        "source_name": title,
                        "publisher": COMPANIES[entity_code],
                        "published_at": f"{published}T00:00:00+08:00",
                        "retrieved_at": retrieved,
                        "original_quote": item["quote"],
                        "locator": item["locator"],
                        "source_url": url,
                        "anchor_at": utc_now(),
                        "source_tier": "T2",
                        "snapshot_path": path,
                        "snapshot_sha256": sha,
                    },
                    "metric": {
                        "metric_code": item["metric_code"],
                        "entity_code": entity_code,
                        "value": item["value"],
                        "unit": item["unit"],
                        "report_period": period,
                        "source_table": "company_monthly_disclosure",
                        "source_row_key": f"{document_id}|{item['metric_code']}|{period}",
                    },
                }
                ingest_record(db_path, payload, initialize_db=False)
                accepted += 1
            with conn:
                conn.execute(
                    """UPDATE quarantine SET status='RESOLVED'
                       WHERE object_id=? AND reason_code LIKE '%MONTHLY_TABLE_NOT_PARSED%'""",
                    (document_id,),
                )
                conn.execute(
                    "UPDATE raw_documents SET parse_status='PARSED',error_message=NULL WHERE document_id=?",
                    (document_id,),
                )
                conn.execute(
                    "UPDATE announcement_catalogue SET status='PARSED',error_message=NULL WHERE announcement_id=?",
                    (announcement_id,),
                )
            imported_documents += 1
            imported_values += accepted
        except (IngestRejected, Exception) as exc:
            message = f"{type(exc).__name__}: {exc}"
            errors.append({"announcement_id": announcement_id, "error": message})
            with conn:
                conn.execute(
                    "UPDATE raw_documents SET parse_status='ERROR',error_message=? WHERE document_id=?",
                    (message, document_id),
                )
                conn.execute(
                    "UPDATE announcement_catalogue SET status='ERROR',error_message=? WHERE announcement_id=?",
                    (message, announcement_id),
                )
    conn.close()
    return {
        "pending_documents": len(rows),
        "imported_documents": imported_documents,
        "imported_values": imported_values,
        "needs_review": needs_review,
        "errors": errors,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    args = parser.parse_args()
    print(json.dumps(import_pending(args.db), ensure_ascii=False, indent=2))
