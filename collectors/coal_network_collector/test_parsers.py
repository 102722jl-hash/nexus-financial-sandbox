import unittest
from parsers import parse_stats_energy, parse_nea_power, parse_ncexc_coal

class ParserTests(unittest.TestCase):
    def test_stats(self):
        facts=parse_stats_energy('<h1>2026年7月份能源生产情况</h1><p>原煤产量35600万吨。</p>'.encode())
        self.assertEqual((facts[0].metric_code,facts[0].value,facts[0].report_period),('RAW_COAL_OUTPUT',35600,'2026-07'))
    def test_nea(self):
        facts=parse_nea_power('<p>2026年1—7月份，全国火电累计平均利用2500小时。</p>'.encode())
        self.assertEqual((facts[0].metric_code,facts[0].value),('UTILIZATION_HOURS_THERMAL',2500))
    def test_coal_price(self):
        facts=parse_ncexc_coal('<p>发布日期2026年08月31日 动力煤5500K价格738元/吨</p>'.encode())
        self.assertEqual((facts[0].value,facts[0].unit),(738,'元/吨'))

if __name__=='__main__': unittest.main()
