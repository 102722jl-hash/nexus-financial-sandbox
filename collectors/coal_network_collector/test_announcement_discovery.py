import unittest
from announcement_discovery import normalize

class DiscoveryTests(unittest.TestCase):
    def test_filter_and_url(self):
        payload={'announcements':[
          {'announcementId':'1','announcementTitle':'2026年上半年发电量、上网电价公告','announcementTime':1,'adjunctUrl':'finalpage/a.PDF'},
          {'announcementId':'2','announcementTitle':'董事会决议公告','announcementTime':2,'adjunctUrl':'finalpage/b.PDF'}]}
        items=normalize('600027.SH',payload)
        self.assertEqual(len(items),1)
        self.assertEqual(items[0]['url'],'https://static.cninfo.com.cn/finalpage/a.PDF')
if __name__=='__main__': unittest.main()
