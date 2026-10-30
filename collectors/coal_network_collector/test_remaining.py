import unittest
from financial_reports import parse_financial_metrics,detect_currency_scale,scale_to_yuan

class RemainingTests(unittest.TestCase):
    def test_financial(self):
        text='金额单位：人民币万元 营业收入 1,234.50 归属于上市公司股东的净利润 56.70'
        values={x['metric_code']:x['value'] for x in parse_financial_metrics(text)}
        self.assertEqual(values['REVENUE'],1234.5); self.assertEqual(values['NET_PROFIT'],56.7)
        self.assertEqual(detect_currency_scale(text),'万元'); self.assertEqual(scale_to_yuan(2,'万元'),20000)
if __name__=='__main__': unittest.main()
