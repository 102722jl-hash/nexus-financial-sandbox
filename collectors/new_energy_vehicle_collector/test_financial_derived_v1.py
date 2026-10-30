from __future__ import annotations

import sqlite3
import unittest
from pathlib import Path

from derived_metrics_v1 import build_derived_metrics
from financial_pdf_parser_v1 import parse_financial_metrics
from ingest_v1 import ingest_record
from initialize import initialize


class FinancialDerivedTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db = Path(__file__).resolve().parent / ".test_financial_derived.db"
        self.db.unlink(missing_ok=True)
        initialize(self.db)

    def tearDown(self) -> None:
        self.db.unlink(missing_ok=True)

    def test_balance_sheet_units_and_debt_sum(self) -> None:
        text = """[[PAGE:1]] 财务报表及附注的单位为：人民币千元
        货币资金 1 58,737,867 75,424,747
        短期借款 24 37,645,979 38,484,710
        一年内到期的非流动负债 32 3,452,964 6,311,964
        长期借款 34 61,201,246 60,705,569
        应付债券 35 14,993,800 4,997,910
        总股本 9,117,197,565 股"""
        metrics = {item["metric_code"]: item for item in parse_financial_metrics(text)}
        self.assertEqual(metrics["CASH"]["value"], 58_737_867_000)
        self.assertEqual(metrics["DEBT_COMPONENTS"]["value"], 117_293_989_000)
        self.assertEqual(metrics["SHARE_CAPITAL"]["value"], 9_117_197_565)

    def test_capex_accepts_pdf_line_breaks_inside_label(self) -> None:
        text = """[[PAGE:20]] 合并现金流量表 单位：元
        购建固定资产、无形资产和
        其他长期资产支付的现金 6,010,879,133.78 4,893,161,882.55"""
        metrics = {item["metric_code"]: item for item in parse_financial_metrics(text)}
        self.assertEqual(metrics["CAPEX"]["value"], 6_010_879_133.78)

    def _ingest(self, metric_code: str, value: float, unit: str, *, as_of_date=None) -> None:
        period = None if as_of_date else "2026-H1"
        key = f"{metric_code}|{period}|{as_of_date}"
        ingest_record(self.db, {
            "evidence": {
                "source_type": "MARKET_PROXY" if metric_code == "CLOSE_PRICE" else "SOURCE_FACT",
                "source_name": "测试来源", "publisher": "测试发布者",
                "published_at": "2026-09-17T15:00:00+08:00",
                "retrieved_at": "2026-09-17T15:01:00+08:00",
                "original_quote": key, "locator": key,
                "source_url": "https://example.invalid/test", "anchor_at": "2026-09-18T00:00:00+08:00",
                "source_tier": "T3" if metric_code == "CLOSE_PRICE" else "T2",
            },
            "metric": {
                "metric_code": metric_code, "entity_code": "002594.SZ", "value": value,
                "unit": unit, "report_period": period, "as_of_date": as_of_date,
                "source_row_key": key,
            },
        })

    def test_derived_values_are_tagged_and_reproducible(self) -> None:
        self._ingest("REVENUE", 1000, "元")
        self._ingest("OPERATING_COST", 700, "元")
        self._ingest("CASH", 400, "元")
        self._ingest("DEBT_COMPONENTS", 900, "元")
        self._ingest("SHARE_CAPITAL", 100, "股")
        self._ingest("CLOSE_PRICE", 12, "元/股", as_of_date="2026-09-17")
        first = build_derived_metrics(self.db)
        second = build_derived_metrics(self.db)
        self.assertEqual(first["created"], 3)
        self.assertEqual(second["created"], 3)
        conn = sqlite3.connect(self.db)
        rows = dict(conn.execute(
            """SELECT metric_code,value FROM metric_values
               WHERE entity_code='002594.SZ' AND source_table='derived_metrics_v1'"""
        ))
        statuses = {row[0] for row in conn.execute(
            """SELECT DISTINCT value_status FROM metric_values
               WHERE entity_code='002594.SZ' AND source_table='derived_metrics_v1'"""
        )}
        conn.close()
        self.assertEqual(rows["GROSS_PROFIT_PROXY"], 300)
        self.assertEqual(rows["NET_DEBT_PROXY"], 500)
        self.assertEqual(rows["CURRENT_MARKET_CAP"], 1200)
        self.assertEqual(statuses, {"CALCULATED_LINEAGE"})


if __name__ == "__main__":
    unittest.main()
