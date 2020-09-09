'''
Created on 22 Jun 2020

@author: riccardo
'''
import unittest
import re
from os.path import join, dirname
from unittest.mock import patch
from io import StringIO

import numpy as np
from obspy.core.stream import read, Stream
from obspy.core.inventory.inventory import read_inventory
from obspy.signal.spectral_estimation import PPSD

from sdaas.model import get_scores
from sdaas.features import get_features_from_traces
from sdaas.run import process, bcolors


def check_output(output, th, sep, color, expected_rows=None):
    out = output.strip().split('\n')
    if expected_rows is not None:
        assert len(out) == expected_rows
    ptr = '\\s+' if sep is None else sep
    for _ in out:
        _ = float(re.split(ptr, _)[3])
        assert _ > 0.3 and _ < 0.9
    numcols = 4
    if th > 0 and th < 1:
        assert all(re.split(ptr, _)[-1] in '01' for _ in out)
        numcols += 1
    assert all(len(re.split(ptr, _)) == numcols for _ in out)
    if color:
        assert all((bcolors.ENDC in _) and
                   (bcolors.OKGREEN in _ or bcolors.WARNING in _)
                   for _ in out)

class Test(unittest.TestCase):

    datadir = join(dirname(__file__), 'data')

    def setUp(self):
        pass

    def tearDown(self):
        pass

#     def test_run_from_station(self):
#         '''tests a particular case of station download from geofon.
#         Needs internet connection
#         '''
#         data = ("http://geofon.gfz-potsdam.de/fdsnws/station/1/query?net=GE"
#                 "&sta=EIL&cha=BH?&start=2020-02-01")
#         with patch('sys.stdout', new=StringIO()) as fakeoutput:
#             process(data)
#             # self.assertEqual(fakeOutput.getvalue().strip(), 'hello world')

    def test_run_from_data_dir(self):
        '''tests a particular case of station download from geofon.
        Needs internet connection
        '''
        sep = None
        for th in [0, 0.5]:
            for color in [False, True]:
                with patch('sys.stdout', new=StringIO()) as fakeoutput:
                    process(join(self.datadir, 'testdir1'),
                            colors=color, threshold=th,
                            # metadata=join(self.datadir, 'GE.FLT1.xml'),
                            capture_stderr=False)
                    captured = fakeoutput.getvalue()
                    expected_rows = 6
                    check_output(captured, th, sep, color,
                                 expected_rows=expected_rows)

#     def test_run_from_data_file(self):
#         '''tests a particular case of station download from geofon.
#         Needs internet connection
#         '''
#         with patch('sys.stdout', new=StringIO()) as fakeoutput:
#             process(join(self.datadir, 'testdir2'),
#                     # metadata=join(self.datadir, 'GE.FLT1.xml'),
#                     capture_stderr=False)
#             captured = fakeoutput.getvalue()
#             lines = captured.split()
#             assert len(lines) == 1
#             assert all(not _.endswith('nan') for _ in lines)


#     def test_run_from_data_dir_bad_inventory(self):
#         with self.assertRaises(Exception) as context:
#             process(join(self.datadir, 'testdir1'),
#                     metadata=join(self.datadir, 'inventory_GE.APE.xml'),
#                     capture_stderr=False)


if __name__ == "__main__":
    #  import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
