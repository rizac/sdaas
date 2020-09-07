'''
Created on 22 Jun 2020

@author: riccardo
'''
import unittest
from os.path import join, dirname
from unittest.mock import patch
from io import StringIO

import numpy as np
from obspy.core.stream import read, Stream
from obspy.core.inventory.inventory import read_inventory
from obspy.signal.spectral_estimation import PPSD

from sdaas.model import get_scores
from sdaas.features import get_features_from_traces
from sdaas.run import process


class Test(unittest.TestCase):


    def setUp(self):
        pass


    def tearDown(self):
        pass


    def test_ppsd(self):
        '''tests a particular case of station download from geofon.
        Needs internet connection
        '''
        data = "http://geofon.gfz-potsdam.de/fdsnws/station/1/query?net=GE&sta=EIL&cha=BH?&start=2020-02-01"
        with patch('sys.stdout', new=StringIO()) as fakeOutput:
            process(data)
            # self.assertEqual(fakeOutput.getvalue().strip(), 'hello world')


if __name__ == "__main__":
    #  import sys;sys.argv = ['', 'Test.testName']
    unittest.main()