"""
Tests runs from the command line

Created on 22 Jun 2020

@author: Riccardo Z. <rizac@gfz-potsdam.de>
"""
import unittest
from datetime import datetime
import re
from os.path import join, dirname
from unittest.mock import patch
from io import StringIO

from sdaas.run import process, is_threshold_set
from sdaas.cli.utils import ansi_colors_escape_codes


def check_output(output, threshold=-1., sep=None, expected_rows=None):
    """check the string output of a score calculation from the command line"""
    out = output.strip().split('\n')
    ptr = '\\s+' if not sep else sep
    out = [re.split(ptr, (_.strip() if not sep else _)) for _ in out]
    # if not sep:  # NOT ANYMORE:
    #     # datetimes are printed with the space, we have to join
    #     # four "fake" col into 2 columns:
    #     out2 = []
    #     for _ in out:
    #         line = [_[0], _[1] + ' ' + _[2], _[3] + ' ' + _[4]] + _[5:]
    #         out2.append(line)
    #     out = out2
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
        assert 0.3 < _ < 0.9  # check score is meaningful (heuristically)
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
    _stdout, _stderr = None, None

    def setUp(self):
        # https://docs.python.org/3.5/library/unittest.mock.html#patch-methods-start-and-stop
        patcher1 = patch('sdaas.run.sys.stdout', new=StringIO())
        self._stdout = patcher1.start()
        self.addCleanup(patcher1.stop)

        patcher2 = patch('sdaas.run.sys.stderr', new=StringIO())
        self._stderr = patcher2.start()
        self.addCleanup(patcher2.stop)

        def mockcolorsaresupportedinterminal(*a, **vv):
            return True
        patcher3 = patch(('sdaas.cli.utils.ansi_colors_escape_codes.'
                          'are_supported_on_current_terminal'),
                          side_effect=mockcolorsaresupportedinterminal)
        patcher3.start()
        self.addCleanup(patcher3.stop)

    @property
    def stdout(self):
        """
        return the captured stdout and resets it so that calling again
        this method  will only return new captured output
        """
        ret = self._stdout.getvalue()
        # Truncate and reset (https://stackoverflow.com/a/4330829):
        self._stdout.truncate(0)
        self._stdout.seek(0)
        return ret

    @property
    def stderr(self):
        """
        return the captured stdout and resets it so that calling again
        this method will only return new captured output
        """
        ret = self._stderr.getvalue()
        # Truncate and reset (https://stackoverflow.com/a/4330829):
        self._stderr.truncate(0)
        self._stderr.seek(0)
        return ret

    def test_run_from_data_dir(self):  # , mock_ansi_colors_escape_codes_supported):
        """
        test scores from several files in directory
        """
        with patch('sdaas.run.ansi_colors_escape_codes.are_supported_on_current_terminal',
                   side_effect=lambda *a, **kw: True):
            for th in [0.5, 0]:
                for sep in ['', ';']:
                    process(join(self.datadir, 'testdir1'),
                            sep=sep, threshold=th,
                            )
                    captured = self.stdout
                    check_output(captured, th, sep, expected_rows=6)

    def test_run_from_data_file(self):
        """
        test a particular case of station download from geofon.
        Needs internet connection
        """
        with patch('sdaas.run.ansi_colors_escape_codes.are_supported_on_current_terminal',
                   side_effect=lambda *a, **kw: True):
            for th in [0.5, 0]:
                for sep in ['', ';']:
                    # test single-file directory:
                    process(join(self.datadir, 'testdir2'),
                            sep=sep, threshold=th,
                            metadata=join(self.datadir, 'inventory_GE.APE.xml'),
                            )
                    captured = self.stdout
                    check_output(captured, th, sep, expected_rows=1)

                    # test single file:
                    process(join(self.datadir, 'testdir2', 'trace_GE.APE.mseed'),
                            sep=sep, threshold=th,
                            metadata=join(self.datadir, 'inventory_GE.APE.xml'),
                            )
                    captured = self.stdout
                    check_output(captured, th, sep, expected_rows=1)

    def test_run_from_data_dir_bad_inventory(self):

        # wrong metadata:
        with self.assertRaises(ValueError) as context:
            process(join(self.datadir, 'testdir1'),
                    metadata=join(self.datadir, 'inventory_GE.APE.xml'))

        # no metadata found in directory
        with self.assertRaises(ValueError) as context:
            process(join(self.datadir, 'testdir2'))

    def test_run_from_http(self):
        url = ('http://geofon.gfz-potsdam.de/fdsnws/station/1/'
               'query?net=GE&sta=EIL&cha=BH?&start=2019-06-01')
        process(url, download_count=10, threshold=0.6)

    def test_run_from_url_no_data(self):
        url = ('http://geofon.gfz-potsdam.de/fdsnws/station/1/'
               'query?net=GE&sta=E?&cha=BH?&start=2019-06-01')
        process(url, threshold=0.6)
        capt = self.stdout
        assert len(capt) == 0

    def test_run_from_url_several(self):
        url = ("http://geofon.gfz-potsdam.de/fdsnws/station/1/query"
               "?net=GE&sta=A*&cha=BH?&start=2019-06-01")
        process(url, download_count=10, threshold=0.6)
        capt = self.stdout
        check_output(capt, threshold=0.6)

    def test_run_from_url_several_aggregate(self):
        url = ("http://geofon.gfz-potsdam.de/fdsnws/station/1/"
               "query?net=CX&sta=PB*&cha=BE?,BH?,BN?"
               "&start=2020-09-14&end=2020-09-24")
        process(url, aggregate='median', download_count=4)
        capt = self.stdout
        check_output(capt)
        # print(capt)
        assert all(0.39 < float(line.split()[-1]) < 0.5 for line in capt.strip().split('\n'))


if __name__ == "__main__":
    #  import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
