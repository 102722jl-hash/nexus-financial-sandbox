"""Conservative parser for key financial metrics in full periodic reports."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from company_pdf_parser_v1 import page_at, pdf_text, utc_now
from contract_v1 import COMPANIES, NETWORK_ID
from ingest_v1 import ingest_record
from initialize import DEFAULT_DB, initialize

NUMBER = r"[-(]?[0-9][0-9,]*(?:\.[0-9]+)?\)?"
SPECS = {
    "REVENUE": [
        rf"营业收入（元）\s*({NUMBER})",
        rf"营业收入\s+({NUMBER})",
    ],
    "OPERATING_COST": [
        rf"营业成本\s+(?:[一二三四五六七八九十]+、)?\d{{1,2}}\s+({NUMBER})",
        rf"营业成本\s+({NUMBER})",
    ],
    "NET_PROFIT": [rf"归属于上市公司股东的净利润(?:（元）)?\s*({NUMBER})"],
    "RND_EXPENSE": [
        rf"研发费用\s+(?:[一二三四五六七八九十]+、)?\d{{1,2}}\s+({NUMBER})",
        rf"研发费用\s+({NUMBER})",
    ],
    "OPERATING_CASH_FLOW": [
        rf"经营活动产生的现金流量净额(?:（元）)?\s*({NUMBER})",
    ],
    "CAPEX": [
        rf"购建固定资产、\s*无形资产和\s*其他长期资产支付的现金\s+({NUMBER})",
    ],
}

BALANCE_SHEET_SPECS = {
    "CASH": [
        rf"货币资金\s+(?:(?:[一二三四五六七八九十]+、)?\d{{1,3}}\s+)?({NUMBER})\s+({NUMBER})",
    ],
    "SHARE_CAPITAL": [
        rf"实收资本（或股本）\s+(?:(?:[一二三四五六七八九十]+、)?\d{{1,3}}\s+)?({NUMBER})\s+({NUMBER})",
        rf"总股本\s+({NUMBER})",
        rf"股本\s+(?:(?:[一二三四五六七八九十]+、)?\d{{1,3}}\s+)?({NUMBER})\s+({NUMBER})",
    ],
}

DEBT_COMPONENT_SPECS = {
    "短期借款": [rf"短期借款\s+(?:(?:[一二三四五六七八九十]+、)?\d{{1,3}}\s+)?({NUMBER})\s+({NUMBER})"],
    "一年内到期的非流动负债": [rf"一年内到期的非流动负债\s+(?:(?:[一二三四五六七八九十]+、)?\d{{1,3}}\s+)?({NUMBER})\s+({NUMBER})"],
    "长期借款": [rf"长期借款\s+(?:(?:[一二三四五六七八九十]+、)?\d{{1,3}}\s+)?({NUMBER})\s+({NUMBER})"],
    "应付债券": [rf"应付债券\s+(?:(?:[一二三四五六七八九十]+、)?\d{{1,3}}\s+)?({NUMBER})\s+({NUMBER})"],
}


def _number(raw: str) -> float:
    value = raw.replace(",", "").strip()
    negative = value.startswith("(") and value.endswith(")")
    value = value.strip("()")
    result = float(value)
    return -result if negative else result


def _unit_factor(text: str, position: int, label: str) -> float:
    if "（元）" in label:
        return 1.0
    # Balance-sheet units are commonly printed in the heading on the previous
    # PDF page, so keep enough context to cross a page break.
    context = text[max(0, position - 12000):position]
    markers = [
        (context.rfind("人民币千元"), 1000.0),
        (context.rfind("单位：千元"), 1000.0),
        (context.rfind("单位:千元"), 1000.0),
        (context.rfind("千元"), 1000.0),
        (context.rfind("单位：万元"), 10000.0),
        (context.rfind("万元"), 10000.0),
        (context.rfind("单位：元"), 1.0),
        (context.rfind("币种：人民币"), 1.0),
    ]
    last_position, factor = max(markers, key=lambda item: item[0])
    return factor if last_position >= 0 else 1.0


def _first_statement_match(text: str, patterns: list[str]) -> re.Match | None:
    """Pick a balance-sheet row with current and prior values, not a narrative mention."""
    for pattern in patterns:
        for match in re.finditer(pattern, text):
            try:
                current = abs(_number(match.group(1)))
            except (IndexError, ValueError):
                continue
            if current >= 1000:
                return match
    return None


def parse_financial_metrics(text: str) -> list[dict]:
    output = []
    for metric_code, patterns in SPECS.items():
        selected = None
        for pattern in patterns:
            for match in re.finditer(pattern, text):
                if abs(_number(match.group(1))) >= 1000:
                    selected = match
                    break
            if selected:
                break
        if not selected:
            continue
        factor = _unit_factor(text, selected.start(), selected.group(0))
        output.append({
            "metric_code": metric_code,
            "value": _number(selected.group(1)) * factor,
            "unit": "元",
            "quote": " ".join(selected.group(0).split()),
            "locator": f"page:{page_at(text, selected.start())};financial-line:{metric_code}",
            "unit_factor": factor,
        })
    revenue = next((abs(item["value"]) for item in output if item["metric_code"] == "REVENUE"), None)
    if revenue:
        for item in output:
            thresholds = {"OPERATING_COST": 0.01, "RND_EXPENSE": 0.001, "CAPEX": 0.001}
            threshold = thresholds.get(item["metric_code"])
            if threshold is None:
                continue
            while 0 < abs(item["value"]) / revenue < threshold and item["unit_factor"] < 10000:
                item["value"] *= 1000
                item["unit_factor"] *= 1000

    for metric_code, patterns in BALANCE_SHEET_SPECS.items():
        selected = _first_statement_match(text, patterns)
        if not selected:
            continue
        factor = 1.0 if metric_code == "SHARE_CAPITAL" else _unit_factor(
            text, selected.start(), selected.group(0)
        )
        output.append({
            "metric_code": metric_code,
            "value": _number(selected.group(1)) * factor,
            "unit": "股" if metric_code == "SHARE_CAPITAL" else "元",
            "quote": " ".join(selected.group(0).split()),
            "locator": f"page:{page_at(text, selected.start())};balance-sheet:{metric_code}",
            "unit_factor": factor,
        })

    debt_components = []
    for label, patterns in DEBT_COMPONENT_SPECS.items():
        selected = _first_statement_match(text, patterns)
        if not selected:
            continue
        factor = _unit_factor(text, selected.start(), selected.group(0))
        debt_components.append({
            "label": label,
            "value": _number(selected.group(1)) * factor,
            "quote": " ".join(selected.group(0).split()),
            "page": page_at(text, selected.start()),
            "unit_factor": factor,
        })
    if debt_components:
        output.append({
            "metric_code": "DEBT_COMPONENTS",
            "value": sum(item["value"] for item in debt_components),
            "unit": "元",
            "quote": "；".join(item["quote"] for item in debt_components),
            "locator": "balance-sheet-sum:" + ",".join(
                f"{item['label']}@page:{item['page']}" for item in debt_components
            ),
            "unit_factor": None,
            "components": {item["label"]: item["value"] for item in debt_components},
        })
    return output


def _published_at(milliseconds: int | None) -> str:
    if milliseconds:
        china = timezone(timedelta(hours=8))
        return datetime.fromtimestamp(milliseconds / 1000, timezone.utc).astimezone(china).isoformat()
    return utc_now()


def import_financial_reports(db_path: Path = DEFAULT_DB) -> dict:
    initialize(db_path)
    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        """SELECT a.announcement_id,a.entity_code,a.title,a.published_ms,a.pdf_url,
                  a.document_id,r.retrieved_at,r.content_sha256,r.snapshot_path
           FROM announcement_catalogue a
           JOIN raw_documents r ON r.document_id=a.document_id
           WHERE a.network_id=? AND a.title LIKE '%半年度报告'
             AND a.title NOT LIKE '%摘要%' AND a.status IN ('DOWNLOADED','NEEDS_REVIEW','PARSED')""",
        (NETWORK_ID,),
    ).fetchall()
    documents = 0
    values = 0
    errors = []
    for row in rows:
        (announcement_id, entity_code, title, published_ms, url, document_id,
         retrieved, sha, path) = row
        try:
            text = pdf_text(Path(path).read_bytes())
            metrics = parse_financial_metrics(text)
            required = {"REVENUE", "OPERATING_COST", "NET_PROFIT", "OPERATING_CASH_FLOW"}
            found = {item["metric_code"] for item in metrics}
            if not required.issubset(found):
                missing = sorted(required - found)
                raise ValueError(f"REQUIRED_FINANCIAL_LINES_MISSING:{missing}")
            published = _published_at(published_ms)
            period_match = re.search(r"(20\d{2})年", title)
            period = f"{period_match.group(1)}-H1" if period_match else None
            for item in metrics:
                key = f"{document_id}|{item['metric_code']}|{item['locator']}|{item['quote']}"
                evidence_id = "evidence::cninfo::" + hashlib.sha256(key.encode("utf-8")).hexdigest()
                payload = {
                    "evidence": {
                        "evidence_id": evidence_id,
                        "source_type": "SOURCE_FACT",
                        "source_name": title,
                        "publisher": COMPANIES[entity_code],
                        "published_at": published,
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
                        "metric_value_id": "metric::financial::" + hashlib.sha256(
                            f"{document_id}|{item['metric_code']}|{period}".encode("utf-8")
                        ).hexdigest(),
                        "metric_code": item["metric_code"],
                        "entity_code": entity_code,
                        "value": item["value"],
                        "unit": item["unit"],
                        "currency": "CNY",
                        "report_period": period,
                        "source_table": "company_financial_report",
                        "source_row_key": f"{document_id}|{item['metric_code']}|{period}",
                    },
                }
                ingest_record(db_path, payload, initialize_db=False)
                values += 1
            with conn:
                conn.execute(
                    "UPDATE raw_documents SET parse_status='PARSED',error_message=NULL WHERE document_id=?",
                    (document_id,),
                )
                conn.execute(
                    "UPDATE announcement_catalogue SET status='PARSED',error_message=NULL WHERE announcement_id=?",
                    (announcement_id,),
                )
            documents += 1
        except Exception as exc:
            message = f"{type(exc).__name__}: {exc}"
            errors.append({"announcement_id": announcement_id, "error": message})
            with conn:
                conn.execute(
                    "UPDATE raw_documents SET parse_status='NEEDS_REVIEW',error_message=? WHERE document_id=?",
                    (message, document_id),
                )
                conn.execute(
                    "UPDATE announcement_catalogue SET status='NEEDS_REVIEW',error_message=? WHERE announcement_id=?",
                    (message, announcement_id),
                )
    conn.close()
    return {
        "pending_documents": len(rows),
        "imported_documents": documents,
        "imported_values": values,
        "errors": errors,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    args = parser.parse_args()
    print(json.dumps(import_financial_reports(args.db), ensure_ascii=False, indent=2))
