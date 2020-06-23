'''
Created on 22 Jun 2020

@author: riccardo
'''
import unittest
from os.path import join, dirname
from obspy.core.stream import read
from obspy.core.inventory.inventory import read_inventory
from sdaas.anomalyscore import get_psd_features


class Test(unittest.TestCase):


    def setUp(self):
        pass


    def tearDown(self):
        pass


    def test_ppsd(self):
        dataroot = join(dirname(__file__), 'data')
        for file, inv, expectedval in (
            [
                join(dataroot, 'trace_GE.APE.mseed'),
                join(dataroot, 'inventory_GE.APE.xml'),
                -132.45200562
            ],
            [
                join(dataroot, 'GE.FLT1..HH?.mseed'),
                join(dataroot, 'GE.FLT1.xml'),
                -136.72659358
            ],
            [
                ('http://service.iris.edu/fdsnws/dataselect/1/query?'
                 '&net=TA&sta=A*&start=2019-01-04T23:22:00&cha=BH?'
                 '&end=2019-01-04T23:24:00'),
                ('http://service.iris.edu/fdsnws/station/1/query?&net=TA'
                 '&sta=A*&start=2019-01-04T23:22:00&cha=BH?'
                 '&end=2019-01-04T23:24:00&level=response'),
                None
            ]
        ):
            # trace, inv = 'GE.FLT1..HH?.mseed', 'GE.FLT1.xml'
            stream = read(file)
            metadata = read_inventory(inv)
            feats = get_psd_features(stream, metadata)
            pasd = 9


if __name__ == "__main__":
    #  import sys;sys.argv = ['', 'Test.testName']
    unittest.main()