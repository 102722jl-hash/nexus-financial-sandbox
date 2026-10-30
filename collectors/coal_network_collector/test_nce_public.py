import unittest
from nce_public import parse
class NceTests(unittest.TestCase):
    def test_parse_public_text(self):
        text='国煤直达动力煤价格指数 5500K 738 元/吨 5000K 650 元/吨 发布日期2026年09月05日'
        values=parse(text)
        self.assertEqual(values[0][:3],('COAL_PRICE_5500',738.0,'2026-09-05'))
        self.assertEqual(values[1][0],'COAL_PRICE_5000')
if __name__=='__main__': unittest.main()
