from __future__ import annotations

import unittest

from company_pdf_parser_v1 import is_monthly_disclosure, parse_monthly_metrics


class CompanyPdfParserTests(unittest.TestCase):
    def test_changan_monthly_nev_production_and_sales(self) -> None:
        text = (
            "[[PAGE:2]] 产品类别 产量（辆） 销量（辆） "
            "新能源汽车 100,009 83,302 20.06% 580,243 581,544 -0.22% "
            "100,496 88,947 12.98% 589,477 620,667 -5.03%"
        )
        parsed = {item["metric_code"]: item for item in parse_monthly_metrics("000625.SZ", text)}
        self.assertEqual(parsed["COMPANY_NEV_PRODUCTION"]["value"], 100_009)
        self.assertEqual(parsed["COMPANY_NEV_SALES"]["value"], 100_496)
        self.assertIn("page:2", parsed["COMPANY_NEV_SALES"]["locator"])

    def test_great_wall_monthly_nev_sales(self) -> None:
        text = (
            "[[PAGE:1]] 8月海外销售62,517台，1-8月累计销售415,958台。"
            "8月新能源车销售40,700台，1-8月累计销售219,985台。"
        )
        parsed = parse_monthly_metrics("601633.SH", text)
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0]["metric_code"], "COMPANY_NEV_SALES")
        self.assertEqual(parsed[0]["value"], 40_700)

    def test_changan_punctuated_title_is_monthly_disclosure(self) -> None:
        self.assertTrue(is_monthly_disclosure("关于2026年8月份产、销快报的公告"))


if __name__ == "__main__":
    unittest.main()
