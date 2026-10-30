from __future__ import annotations

import unittest

from industry_public_v1 import parse_report


class PublicCollectorParserTests(unittest.TestCase):
    def test_cada_monthly_wholesale_scope(self) -> None:
        text = (
            "2026年8月份全国乘用车市场分析 "
            "时间: 2026-09-09 17:41:54 "
            "8月新能源乘用车批发销量达到151.0万辆，同比增长16.4%；"
            "8月新能源车厂商批发渗透率64.2%，较上年提升。"
        )
        parsed = parse_report(text)
        self.assertEqual(parsed["period"], "2026-08")
        self.assertEqual(parsed["sales"], 1_510_000)
        self.assertEqual(parsed["penetration"], 64.2)
        self.assertEqual(parsed["published_at"], "2026-09-09T17:41:54+08:00")


if __name__ == "__main__":
    unittest.main()
