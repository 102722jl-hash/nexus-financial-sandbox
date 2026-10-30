"""Auditable page-level extraction for full company periodic reports."""
from __future__ import annotations

import hashlib
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from pypdf import PdfReader

from company_announcements import COMPANIES, company_code

ROOT = Path(__file__).parent
NETWORK_ID = "coal_power_v1"
PROCESSOR = "deep_report_metrics"
VERSION = "4"
NUM = r"[0-9][0-9,]*(?:\.[0-9]+)?"
BIG_NUM = r"[0-9][0-9,]{4,}(?:\.[0-9]+)?"


@dataclass(frozen=True)
class Fact:
    metric_code: str
    value: float
    unit: str
    page: int
    quote: str
    currency: str | None = None


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def compact(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def number(value: str) -> float:
    return float(value.replace(",", ""))


def published_from_url(url: str) -> str | None:
    match = re.search(r"/(20\d{2})-(\d{2})-(\d{2})/", urlparse(url).path)
    return "-".join(match.groups()) if match else None


def report_metadata(pages: list[str], url: str) -> tuple[str, str, str] | None:
    header = " ".join(pages[:3])
    match = re.search(r"(20\d{2})\s*年半年度报告", header)
    if not match:
        return None
    year = match.group(1)
    published = published_from_url(url)
    if not published:
        return None
    return f"{year}-上半年", f"{year}-06-30", published


def is_full_periodic_report(pages: list[str]) -> bool:
    head = " ".join(pages[:5])
    return (
        bool(re.search(r"20\d{2}\s*年半年度报告", head))
        and "合并资产负债表" in " ".join(pages)
    )


def capture(
    facts: list[Fact],
    pages: list[str],
    metric_code: str,
    unit: str,
    patterns: list[str],
    scale: float = 1.0,
    currency: str | None = None,
    page_numbers: list[int] | None = None,
) -> bool:
    candidates = page_numbers or list(range(1, len(pages) + 1))
    for page_no in candidates:
        text = pages[page_no - 1]
        for pattern in patterns:
            match = re.search(pattern, text, re.I)
            if match:
                facts.append(
                    Fact(
                        metric_code,
                        round(number(match.group("v")) * scale, 2),
                        unit,
                        page_no,
                        compact(match.group(0)),
                        currency,
                    )
                )
                return True
    return False


def pages_with(pages: list[str], needle: str) -> list[int]:
    return [index for index, text in enumerate(pages, 1) if needle in text]


def statement_window(pages: list[str], heading: str, width: int = 3) -> list[int]:
    starts = pages_with(pages, heading)
    if not starts:
        return []
    start = starts[0]
    return list(range(start, min(len(pages), start + width - 1) + 1))


def extract_balance_and_cashflow(pages: list[str], facts: list[Fact]) -> None:
    balance = statement_window(pages, "合并资产负债表", 3)
    if balance:
        balance_text = " ".join(pages[p - 1] for p in balance)
        scale = 1000.0 if "人民币千元" in balance_text else 1.0
        for code, label in [
            ("CASH", r"货币资金"),
            ("SHORT_TERM_DEBT", r"短期借款"),
            ("CURRENT_NONCURRENT_DEBT", r"一年内到期的非流动负债"),
            ("LONG_TERM_DEBT", r"长期借款"),
            ("BONDS_PAYABLE", r"应付债券"),
        ]:
            capture(
                facts,
                pages,
                code,
                "元",
                [rf"{label}(?:\s+\S+){{0,3}}?\s+(?P<v>{BIG_NUM})"],
                scale,
                "CNY",
                balance,
            )
        if scale == 1.0:
            capture(
                facts,
                pages,
                "SHARE_CAPITAL",
                "股",
                [
                    rf"实收资本（或股本）(?:\s+\S+){{0,3}}?\s+(?P<v>{BIG_NUM})",
                    rf"股本(?:\s+\S+){{0,3}}?\s+(?P<v>{BIG_NUM})",
                ],
                page_numbers=balance,
            )

    cashflow = statement_window(pages, "合并现金流量表", 4)
    if cashflow:
        cashflow_text = " ".join(pages[p - 1] for p in cashflow)
        scale = 1000.0 if "人民币千元" in cashflow_text else 1.0
        capture(
            facts,
            pages,
            "OPERATING_CASH_FLOW",
            "元",
            [rf"经营活动产生的现金流\s*量净\s*额(?:\s+\S+){{0,2}}?\s+(?P<v>-?{BIG_NUM})"],
            scale,
            "CNY",
            cashflow,
        )
        capture(
            facts,
            pages,
            "CAPEX",
            "元",
            [
                rf"购建固定资产、无形资产和\s*其他\s*长期资产支付的现金\s+(?P<v>{BIG_NUM})",
                rf"购建固定资产、无形资产和\s*其他长期资产支付\s*的现金\s+(?P<v>{BIG_NUM})",
            ],
            scale,
            "CNY",
            cashflow,
        )


def extract_huaneng(pages: list[str], facts: list[Fact]) -> None:
    ops = pages_with(pages, "公司拥有可控发电装机容量")
    capture(facts, pages, "REVENUE", "元", [rf"公司实现营业收入人民币\s*(?P<v>{NUM})\s*亿元"], 1e8, "CNY", ops)
    capture(facts, pages, "NET_PROFIT", "元", [rf"归属于母公司股东的净利润人民币\s*(?P<v>{NUM})\s*亿元"], 1e8, "CNY", ops)
    capture(facts, pages, "OPERATING_COST", "元", [rf"营业成本人民币\s*(?P<v>{NUM})\s*亿元"], 1e8, "CNY", ops)
    capture(facts, pages, "CONTROLLABLE_CAPACITY", "兆瓦", [rf"拥有可控发电装机容量\s*(?P<v>{NUM})\s*兆瓦"], page_numbers=ops)
    capture(facts, pages, "ON_GRID_TARIFF", "元/兆瓦时", [rf"平均上网结算电价为人民币\s*(?P<v>{NUM})\s*元/兆瓦时"], currency="CNY", page_numbers=ops)
    capture(facts, pages, "GRID_SALES_POWER", "亿千瓦时", [rf"累计完成上网电量\s*(?P<v>{NUM})\s*亿千瓦时"], page_numbers=ops)
    capture(facts, pages, "UTILIZATION_HOURS", "小时", [rf"累计平均利用小时\s*(?P<v>{NUM})\s*小时"], page_numbers=ops)
    capture(facts, pages, "THERMAL_UTILIZATION_HOURS", "小时", [rf"燃煤机组利用小时\s*(?P<v>{NUM})\s*小时"], page_numbers=ops)
    capture(facts, pages, "COAL_PROCUREMENT_VOLUME", "万吨", [rf"累计采购煤炭\s*(?P<v>{NUM})\s*万吨"], page_numbers=ops)
    capture(facts, pages, "STANDARD_COAL_PRICE", "元/吨", [rf"发电耗用标煤单价人民币\s*(?P<v>{NUM})\s*元/吨"], currency="CNY", page_numbers=ops)
    capture(facts, pages, "SUPPLY_COAL_CONSUMPTION", "克/千瓦时", [rf"供电煤耗为\s*(?P<v>{NUM})\s*克/千瓦时"], page_numbers=ops)
    capture(facts, pages, "PLANT_USE_RATE", "%", [rf"厂用电率为\s*(?P<v>{NUM})%"], page_numbers=ops)


def extract_huadian(pages: list[str], facts: list[Fact]) -> None:
    ops = pages_with(pages, "本公司的主要业绩驱动因素")
    capture(facts, pages, "POWER_GENERATION", "亿千瓦时", [rf"完成发电量\s*(?P<v>{NUM})\s*亿千瓦时"], page_numbers=ops)
    capture(facts, pages, "GRID_SALES_POWER", "亿千瓦时", [rf"完成上网电量\s*(?P<v>{NUM})\s*亿千瓦\s*时"], page_numbers=ops)
    capture(facts, pages, "ON_GRID_TARIFF", "元/兆瓦时", [rf"平均上网电价约为人民币\s*(?P<v>{NUM})\s*元/兆瓦时"], currency="CNY", page_numbers=ops)
    capture(facts, pages, "STANDARD_COAL_PRICE", "元/吨", [rf"入炉煤折标煤单价为\s*(?P<v>{NUM})\s*元/吨"], currency="CNY", page_numbers=ops)
    company = pages_with(pages, "本公司发电机组的平均利用小时")
    capture(facts, pages, "CONTROLLABLE_CAPACITY", "万千瓦", [rf"控股装机容量(?:为)?\s*(?P<v>{NUM})\s*万千\s*瓦"], page_numbers=company)
    capture(facts, pages, "UTILIZATION_HOURS", "小时", [rf"平均利用小时为\s*(?P<v>{NUM})\s*小时"], page_numbers=company)
    capture(facts, pages, "THERMAL_UTILIZATION_HOURS", "小时", [rf"燃煤发电机组的利用小时为\s*(?P<v>{NUM})\s*小时"], page_numbers=company)
    finance = pages_with(pages, "财务报表相关科目变动分析表")
    capture(facts, pages, "REVENUE", "元", [rf"营业收入\s+(?P<v>{BIG_NUM})\s+{BIG_NUM}"], 1000.0, "CNY", finance)
    capture(facts, pages, "OPERATING_COST", "元", [rf"营业成本\s+(?P<v>{BIG_NUM})\s+{BIG_NUM}"], 1000.0, "CNY", finance)
    capture(facts, pages, "OPERATING_CASH_FLOW", "元", [rf"经营活动产生的现金流量净额\s+(?P<v>{BIG_NUM})\s+{BIG_NUM}"], 1000.0, "CNY", finance)
    capture(facts, pages, "FUEL_COST", "元", [rf"燃料成本约为人民币\s*(?P<v>{NUM})\s*亿元"], 1e8, "CNY", finance)
    capture(facts, pages, "DEPRECIATION_AMORTIZATION", "元", [rf"折旧及摊销费用约为人民币\s*(?P<v>{NUM})\s*亿元"], 1e8, "CNY", finance)
    capture(facts, pages, "NET_PROFIT", "元", [rf"归属于上市公司股东的净利润[^。]{{0,20}}人民币\s*(?P<v>{NUM})\s*亿元"], 1e8, "CNY", company)


def extract_guodian(pages: list[str], facts: list[Fact]) -> None:
    summary = pages_with(pages, "主要经济技术指标完成情况如下")
    detail = pages_with(pages, "公司控股装机中火电")
    finance = pages_with(pages, "财务报表相关科目变动分析表")
    capture(facts, pages, "REVENUE", "元", [rf"营业收入[：:]\s*(?P<v>{NUM})\s*亿元"], 1e8, "CNY", summary)
    capture(facts, pages, "NET_PROFIT", "元", [rf"归属于上市公司股东的净利润[：:]\s*(?P<v>{NUM})\s*亿元"], 1e8, "CNY", summary)
    capture(facts, pages, "OPERATING_COST", "元", [rf"营业成本\s+(?P<v>{BIG_NUM})\s+{BIG_NUM}"], 1.0, "CNY", finance)
    capture(facts, pages, "OPERATING_CASH_FLOW", "元", [rf"经营活动产生的现金流量净额\s+(?P<v>{BIG_NUM})\s+{BIG_NUM}"], 1.0, "CNY", finance)
    capture(facts, pages, "POWER_GENERATION", "亿千瓦时", [rf"发电量\s*(?P<v>{NUM})\s*亿千瓦时"], page_numbers=summary)
    capture(facts, pages, "GRID_SALES_POWER", "亿千瓦时", [rf"上网电量\s*(?P<v>{NUM})\s*亿千瓦时"], page_numbers=summary)
    capture(facts, pages, "UTILIZATION_HOURS", "小时", [rf"发电利用小时\s*(?P<v>{NUM})\s*小时"], page_numbers=summary)
    capture(facts, pages, "STANDARD_COAL_PRICE", "元/吨", [rf"入炉综合标煤单价[：:]\s*(?P<v>{NUM})\s*元/吨"], currency="CNY", page_numbers=summary)
    capture(facts, pages, "SUPPLY_COAL_CONSUMPTION", "克/千瓦时", [rf"供电煤耗[：:]\s*(?P<v>{NUM})\s*克/千瓦时"], page_numbers=summary)
    capture(facts, pages, "PLANT_USE_RATE", "%", [rf"发电厂用电率[：:]\s*(?P<v>{NUM})%"], page_numbers=summary)
    capture(facts, pages, "FIXED_ASSET_INVESTMENT", "元", [rf"固定资产投资\s*(?P<v>{NUM})\s*亿元"], 1e8, "CNY", summary)
    capture(facts, pages, "CONTROLLABLE_CAPACITY", "万千瓦", [rf"控股装机容量\s*(?P<v>{NUM})\s*万千瓦"], page_numbers=detail)
    capture(facts, pages, "THERMAL_CAPACITY", "万千瓦", [rf"控股装机中火电\s*(?P<v>{NUM})\s*万千瓦"], page_numbers=detail)
    capture(facts, pages, "THERMAL_POWER_GENERATION", "亿千瓦时", [rf"火电企业累计完成发电量\s*(?P<v>{NUM})\s*亿千瓦时"], page_numbers=detail)
    capture(facts, pages, "THERMAL_GRID_SALES_POWER", "亿千瓦时", [rf"火电企业累计完成发电量\s*{NUM}\s*亿千瓦时，上网\s*电量\s*(?P<v>{NUM})\s*亿千瓦时"], page_numbers=detail)
    capture(facts, pages, "ON_GRID_TARIFF", "元/兆瓦时", [rf"平均上网电价\s*(?P<v>{NUM})\s*元/兆瓦时"], currency="CNY", page_numbers=detail)
    capture(facts, pages, "THERMAL_UTILIZATION_HOURS", "小时", [rf"火电完成\s*(?P<v>{NUM})\s*小时"], page_numbers=detail)
    capture(facts, pages, "COAL_PROCUREMENT_VOLUME", "万吨", [rf"采购原煤\s*(?P<v>{NUM})\s*万吨"], page_numbers=detail)
    capture(facts, pages, "STANDARD_COAL_INPUT", "万吨", [rf"入炉标煤量\s*(?P<v>{NUM})\s*万吨"], page_numbers=detail)


EXTRACTORS = {
    "600011.SH": extract_huaneng,
    "600027.SH": extract_huadian,
    "600795.SH": extract_guodian,
}


def store_fact(
    db: sqlite3.Connection,
    row: tuple,
    code: str,
    period: str,
    period_end: str,
    published: str,
    fact: Fact,
) -> int:
    doc_id, url, name, retrieved, sha, path = row
    locator = f"page:{fact.page};deep-report-v3:{fact.metric_code}"
    evidence_id = "ev_" + hashlib.sha256(f"{doc_id}|{locator}|{fact.quote}".encode()).hexdigest()[:24]
    db.execute(
        """INSERT OR IGNORE INTO evidence(
        evidence_id,source_type,source_name,publisher,published_at,retrieved_at,
        original_quote,page_or_locator,locator,source_url,anchor_at,declared_role,
        data_cutoff,source_tier,temporal_role,snapshot_path,snapshot_sha256,
        raw_storage_status,supports_node_ids,acceptance_status,review_status,acceptance_reason,
        source_table,source_column,source_row_key)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            evidence_id, "EXCHANGE_DISCLOSURE", f"{name}定期报告", name, published, retrieved,
            fact.quote, locator, locator, url, period_end, "AS_OF_EVIDENCE", published,
            "T2", "AS_OF_EVIDENCE", path, sha, "STORED", "[]", "ACCEPTED", "ACCEPTED",
            "PAGE_LEVEL_RULE_AND_UNIT_GATE_PASSED", "deep_financial_report_v3",
            fact.metric_code, doc_id,
        ),
    )
    metric_id = "mv_" + hashlib.sha256(
        f"{doc_id}|{fact.metric_code}|{period}|{fact.value}|{evidence_id}".encode()
    ).hexdigest()[:24]
    db.execute(
        """INSERT OR IGNORE INTO metric_values(
        network_id,metric_value_id,metric_code,entity_code,value,unit,currency,
        report_period,announcement_date,as_of_date,data_cutoff,value_status,evidence_id,
        source_table,source_column,source_row_key)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            NETWORK_ID, metric_id, fact.metric_code, code, fact.value, fact.unit,
            fact.currency, period, published, period_end, published, "SOURCE_FACT",
            evidence_id, "deep_financial_report_v3", fact.metric_code, doc_id,
        ),
    )
    return db.execute("SELECT changes()").fetchone()[0]


def run(db: sqlite3.Connection) -> dict:
    db.execute(
        """CREATE TABLE IF NOT EXISTS document_processors(
        document_id TEXT,processor TEXT,processor_version TEXT,status TEXT,
        processed_at TEXT,error_message TEXT,
        PRIMARY KEY(document_id,processor,processor_version))"""
    )
    rows = db.execute(
        """SELECT document_id,source_url,source_name,retrieved_at,content_sha256,snapshot_path
        FROM raw_documents
        WHERE document_id LIKE 'company_%' AND snapshot_path IS NOT NULL
        AND NOT EXISTS(
          SELECT 1 FROM document_processors p
          WHERE p.document_id=raw_documents.document_id AND p.processor=?
          AND p.processor_version=?)""",
        (PROCESSOR, VERSION),
    ).fetchall()
    result = {"documents_seen": len(rows), "reports_parsed": 0, "facts_inserted": 0, "not_applicable": 0, "errors": []}
    for row in rows:
        doc_id, url, _name, _retrieved, _sha, path = row
        try:
            raw_pages = [page.extract_text() or "" for page in PdfReader(path).pages]
            pages = [compact(text) for text in raw_pages]
            metadata = report_metadata(pages, url)
            code = company_code(" ".join(pages[:5]))
            if not metadata or code not in EXTRACTORS or not is_full_periodic_report(pages):
                db.execute("INSERT OR REPLACE INTO document_processors VALUES(?,?,?,?,?,?)", (doc_id, PROCESSOR, VERSION, "NOT_APPLICABLE", now(), None))
                result["not_applicable"] += 1
                continue
            period, period_end, published = metadata
            facts: list[Fact] = []
            EXTRACTORS[code](pages, facts)
            extract_balance_and_cashflow(pages, facts)
            unique = {fact.metric_code: fact for fact in facts}
            if len(unique) < 8:
                raise ValueError(f"INSUFFICIENT_STABLE_FACTS:{len(unique)}")

            # Replace only fields that V3 actually extracted.  Fields absent from
            # the page-level parser must keep their validated legacy facts rather
            # than falling back to an older quarter or an unrelated statement.
            codes = sorted({fact.metric_code for fact in unique.values()})
            marks = ",".join("?" for _ in codes)
            old_evidence = [
                r[0] for r in db.execute(
                    f"""SELECT evidence_id FROM metric_values
                    WHERE source_row_key=? AND source_table IN ('financial_report','company_announcement')
                    AND metric_code IN ({marks})
                    AND value_status IN ('SOURCE_FACT','CALCULATED')""",
                    (doc_id, *codes),
                )
            ]
            db.execute(
                f"""UPDATE metric_values SET value_status='SUPERSEDED_PARSE_V3'
                WHERE source_row_key=? AND source_table IN ('financial_report','company_announcement')
                AND metric_code IN ({marks})
                AND value_status IN ('SOURCE_FACT','CALCULATED')""",
                (doc_id, *codes),
            )
            if old_evidence:
                evidence_marks = ",".join("?" for _ in old_evidence)
                db.execute(
                    f"""UPDATE evidence SET acceptance_status='SUPERSEDED',
                    review_status='SUPERSEDED',acceptance_reason='REPLACED_BY_PAGE_LEVEL_V3'
                    WHERE evidence_id IN ({evidence_marks})""",
                    old_evidence,
                )
            for fact in unique.values():
                result["facts_inserted"] += store_fact(db, row, code, period, period_end, published, fact)
            db.execute("INSERT OR REPLACE INTO document_processors VALUES(?,?,?,?,?,?)", (doc_id, PROCESSOR, VERSION, "PARSED", now(), None))
            result["reports_parsed"] += 1
        except Exception as exc:
            message = f"{doc_id}:{exc}"
            result["errors"].append(message)
            db.execute("INSERT OR REPLACE INTO document_processors VALUES(?,?,?,?,?,?)", (doc_id, PROCESSOR, VERSION, "ERROR", now(), str(exc)))
    db.commit()
    return result


if __name__ == "__main__":
    import json

    connection = sqlite3.connect(ROOT / "coal_network.db")
    connection.execute("PRAGMA foreign_keys=ON")
    print(json.dumps(run(connection), ensure_ascii=False, indent=2))
    connection.close()
