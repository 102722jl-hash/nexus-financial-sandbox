import unittest
from pathlib import Path
class AutoCollectTests(unittest.TestCase):
    def test_sources_doc_exists(self):
        self.assertTrue(Path(__file__).with_name('SOURCE-RECOMMENDATION.md').exists())
if __name__=='__main__': unittest.main()
