'''
Created on 22 Jun 2020

@author: riccardo
'''
import unittest
import re
from os.path import join, dirname
from unittest.mock import patch
from io import StringIO

from sdaas.run import process
from sdaas.utils.cli import ansi_colors_escape_codes


def check_output(output, threshold, sep, color, expected_rows=None):
    '''checks the string output of a score calculation from the command line'''
    out = output.strip().split('\n')
    if expected_rows is not None:  # check num of rows (if given)
        assert len(out) == expected_rows
    ptr = '\\s+' if sep is None else sep
    is_th_set = 0 < threshold < 1
    colors = color and sep and is_th_set
    for _ in out:
        score_str = re.split(ptr, _)[3]
        if colors:
            # remove ansi colors from score
            score_str = score_str.replace(ansi_colors_escape_codes.ENDC, '').\
                replace(ansi_colors_escape_codes.OKGREEN, '').\
                replace(ansi_colors_escape_codes.WARNING, '')
        _ = float(score_str)  # check score is a float
        assert _ > 0.3 and _ < 0.9  # check score is meaningful (heuristically)
    numcols = 4
    if is_th_set:
        # check class labal ('1': outlier, '0': inlier) is the last column:
        assert all(re.split(ptr, _)[-1] in '01' for _ in out)
        numcols += 1
    # check the correct number of columns (if th_set, it has one more column):
    assert all(len(re.split(ptr, _)) == numcols for _ in out)
    # check colors are printed:
    if colors:
        assert all((ansi_colors_escape_codes.ENDC in _) and
                   (ansi_colors_escape_codes.OKGREEN in _ or
                    ansi_colors_escape_codes.WARNING in _)
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

#     @patch('sdaas.run.ansi_colors_escape_codes.are_supported_on_current_terminal',
#            side_effect=lambda *a, **kw: True)
    def test_run_from_data_dir(self):  # , mock_ansi_colors_escape_codes_supported):
        '''tests a particular case of station download from geofon.
        Needs internet connection
        '''
        sep = None
        with patch('sdaas.run.ansi_colors_escape_codes.are_supported_on_current_terminal',
                   side_effect=lambda *a, **kw: True):
            for th in [0.5, 0]:
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

#     @patch('sdaas.run.ansi_colors_escape_codes.are_supported_on_current_terminal',
#            side_effect=lambda *a, **kw: True)
    def test_run_from_data_file(self):
        '''tests a particular case of station download from geofon.
        Needs internet connection
        '''
        sep = None
        with patch('sdaas.run.ansi_colors_escape_codes.are_supported_on_current_terminal',
                   side_effect=lambda *a, **kw: True):
            for th in [0.5, 0]:
                for color in [False, True]:
                    with patch('sys.stdout', new=StringIO()) as fakeoutput:
                        process(join(self.datadir, 'testdir2'),
                                colors=color, threshold=th,
                                # metadata=join(self.datadir, 'GE.FLT1.xml'),
                                capture_stderr=False)
                        captured = fakeoutput.getvalue()
                        expected_rows = 1
                        check_output(captured, th, sep, color,
                                     expected_rows=expected_rows)

    def test_run_from_data_dir_bad_inventory(self):
        with self.assertRaises(Exception) as context:
            process(join(self.datadir, 'testdir1'),
                    metadata=join(self.datadir, 'inventory_GE.APE.xml'),
                    capture_stderr=False)


if __name__ == "__main__":
    #  import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
