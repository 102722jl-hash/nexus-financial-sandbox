import unittest
from akshare_market import number
class AkshareMarketTests(unittest.TestCase):
    def test_number(self):
        self.assertEqual(number('156,000.25 万股'),156000.25)
        self.assertIsNone(number('暂无'))
if __name__=='__main__': unittest.main()
