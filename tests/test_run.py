'''
Created on 22 Jun 2020

@author: riccardo
'''
import unittest
from datetime import datetime
import re
from os.path import join, dirname
from unittest.mock import patch
from io import StringIO

from sdaas.run import process, is_threshold_set
from sdaas.cli.utils import ansi_colors_escape_codes


def check_output(output, threshold, sep, expected_rows=None):
    '''checks the string output of a score calculation from the command line'''
    out = output.strip().split('\n')
    ptr = '\\s+' if not sep else sep
    out = [re.split(ptr, _) for _ in out]
    if not sep:
        # datetimes are printed with the space, we have to join
        # four "fake" col into 2 columns:
        out2 = []
        for _ in out:
            line = [_[0], _[1] + ' ' + _[2], _[3] + ' ' + _[4]] + _[5:]
            out2.append(line)
        out = out2
    if expected_rows is not None:  # check num of rows (if given)
        assert len(out) == expected_rows
    is_th_set = is_threshold_set(threshold)
    colors = not sep and is_th_set
    for row in out:
        score_str = row[-1 if not is_th_set else -2]
        if colors:
            # remove ansi colors from score
            score_str = score_str.replace(ansi_colors_escape_codes.ENDC, '').\
                replace(ansi_colors_escape_codes.OKGREEN, '').\
                replace(ansi_colors_escape_codes.WARNING, '')
        _ = float(score_str)  # check score is a float
        assert _ > 0.3 and _ < 0.9  # check score is meaningful (heuristically)
    numcols = 4
    if is_th_set:
        for row in out:
            anomaly_class = row[-1]
            if colors:
                # remove ansi colors from score
                anomaly_class = \
                    anomaly_class.replace(ansi_colors_escape_codes.ENDC, '').\
                    replace(ansi_colors_escape_codes.OKGREEN, '').\
                    replace(ansi_colors_escape_codes.WARNING, '')
            _ = int(anomaly_class)  # check score is a int
        # check class labal ('1': outlier, '0': inlier) is the last column:
        assert _ in (0, 1)
        numcols += 1
    # check the correct number of columns (if th_set, it has one more column):
    assert all(len(row) == numcols for row in out)
    # check datetimes:
    for row in out:
        datetime.fromisoformat(row[1])
        datetime.fromisoformat(row[2])
    # check colors are printed:
    if colors:
        for row in out:
            cells2check = row[-2:] if is_th_set else row[-1:]
            assert all((ansi_colors_escape_codes.ENDC in _) and
                       (ansi_colors_escape_codes.OKGREEN in _ or
                        ansi_colors_escape_codes.WARNING in _)
                       for _ in cells2check)


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

    def tst_run_from_data_dir(self):  # , mock_ansi_colors_escape_codes_supported):
        '''tests scores from several files in directory 
        '''
        with patch('sdaas.run.ansi_colors_escape_codes.are_supported_on_current_terminal',
                   side_effect=lambda *a, **kw: True):
            for th in [0.5, 0]:
                for sep in ['', ';']:
                    with patch('sys.stdout', new=StringIO()) as fakeoutput:
                        process(join(self.datadir, 'testdir1'),
                                sep=sep, threshold=th,
                                # metadata=join(self.datadir, 'GE.FLT1.xml'),
                                capture_stderr=False)
                        captured = fakeoutput.getvalue()
                        expected_rows = 6
                        check_output(captured, th, sep,
                                     expected_rows=expected_rows)

    def tst_run_from_data_file(self):
        '''tests a particular case of station download from geofon.
        Needs internet connection
        '''
        with patch('sdaas.run.ansi_colors_escape_codes.are_supported_on_current_terminal',
                   side_effect=lambda *a, **kw: True):
            for th in [0.5, 0]:
                for sep in ['', ';']:
                    # test single-file directory:
                    with patch('sys.stdout', new=StringIO()) as fakeoutput:
                        process(join(self.datadir, 'testdir2'),
                                sep=sep, threshold=th,
                                metadata=join(self.datadir, 'inventory_GE.APE.xml'),
                                capture_stderr=False)
                        captured = fakeoutput.getvalue()
                        expected_rows = 1
                        check_output(captured, th, sep,
                                     expected_rows=expected_rows)

                    # test single file:
                    with patch('sys.stdout', new=StringIO()) as fakeoutput:
                        process(join(self.datadir, 'testdir2', 'trace_GE.APE.mseed'),
                                sep=sep, threshold=th,
                                metadata=join(self.datadir, 'inventory_GE.APE.xml'),
                                capture_stderr=False)
                        captured = fakeoutput.getvalue()
                        expected_rows = 1
                        check_output(captured, th, sep,
                                     expected_rows=expected_rows)

    def tst_run_from_data_dir_bad_inventory(self):

        # wrong metadata:
        with self.assertRaises(Exception) as context:
            process(join(self.datadir, 'testdir1'),
                    metadata=join(self.datadir, 'inventory_GE.APE.xml'),
                    capture_stderr=False)

        # no metadata found in directory
        with self.assertRaises(Exception) as context:
            process(join(self.datadir, 'testdir2'),
                    # metadata=join(self.datadir, 'inventory_GE.APE.xml'),
                    capture_stderr=False)


    def tst_run_from_http(self):
        url = ('http://geofon.gfz-potsdam.de/fdsnws/station/1/'
               'query?net=GE&sta=EIL&cha=BH?&start=2019-06-01')
        process(url, capture_stderr=False, download_count=10, threshold=0.6)

    def tst_run_from_url_no_data(self):
        url = ('http://geofon.gfz-potsdam.de/fdsnws/station/1/'
               'query?net=GE&sta=E?&cha=BH?&start=2019-06-01')
        process(url, capture_stderr=False, download_count=10, threshold=0.6)
        
    def tst_run_from_url_several(self):
        url = ("http://geofon.gfz-potsdam.de/fdsnws/station/1/query"
               "?net=GE&sta=A*&cha=BH?&start=2019-06-01")
        process(url, capture_stderr=False, download_count=10, threshold=0.6)

    def test_run_from_url_several_aggregate(self):
        url = ("http://geofon.gfz-potsdam.de/fdsnws/station/1/query"
               "?net=GE&sta=A*&cha=BH?&start=2019-06-01")
        process(url, aggregate='median',
                capture_stderr=False, download_count=10, threshold=0.6)
        
if __name__ == "__main__":
    #  import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
