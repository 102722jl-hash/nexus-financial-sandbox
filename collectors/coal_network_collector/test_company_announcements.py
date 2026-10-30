import unittest
from company_announcements import company_code,published_date,report_period,parse_metrics

TEXT='''[[PAGE:1]] 华电国际电力股份有限公司 证券代码：600027
2026年上半年发电量、上网电价及机组投产公告
公司完成发电量 1200.50 亿千瓦时，上网电量 1120.25 亿千瓦时。
平均上网电价 420.30 元/兆瓦时。2026年7月24日'''

class CompanyAnnouncementTests(unittest.TestCase):
    def test_metadata(self):
        self.assertEqual(company_code(TEXT),'600027.SH')
        self.assertEqual(published_date(TEXT),'2026-07-24')
        self.assertEqual(report_period(TEXT),'2026-上半年')
    def test_metrics(self):
        values={(x['metric_code'],x['value']) for x in parse_metrics(TEXT)}
        self.assertIn(('POWER_GENERATION',1200.5),values)
        self.assertIn(('GRID_SALES_POWER',1120.25),values)
        self.assertIn(('ON_GRID_TARIFF',420.3),values)
if __name__=='__main__': unittest.main()
