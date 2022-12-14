"""
Tests the Python snippets provided in the README to assure that they work and, if any
output is generated, adds it below the snippet (with a tag marking the code block
as auto generated. Each time this test is run, the auto generated
code is recognized by its tag and deleted before re-executing the snippets)

Created on 28 Sep 2020

@author: Riccardo Z. <rizac@gfz-potsdam.de>
"""
import os
import re
import sys
import numpy as np
import unittest
from io import StringIO
from os.path import join, dirname, relpath, abspath, basename
import json

from obspy.core.stream import read
from obspy.core.inventory.inventory import read_inventory


class Test(unittest.TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_readme(self):
        """test the README code snippets"""
        test_snippet_01()
        test_snippet_02()
        test_snippet_03()
        test_snippet_04()
        test_snippet_05()
        test_snippet_06()


def test_snippet_01():
    snippet = """
from obspy.core.inventory.inventory import read_inventory
from obspy.core.stream import read

from sdaas.core import traces_scores

# Load a Stream object and its inventory
# (use as example the test directory of the package):
stream = read('./tests/data/GE.FLT1..HH?.mseed')
inventory = read_inventory('./tests/data/GE.FLT1.xml')

# Compute the Stream anomaly score (3 scores, one for each Trace):
output = traces_scores(stream, inventory)
"""
    locals_ = {}
    exec_snippet(snippet, locals_)
    assert np.allclose(locals_['output'], [0.45729656, 0.45199387, 0.45113142],
                       atol=0.01, rtol=0)


def test_snippet_02():
    snippet = """
from obspy.core.inventory.inventory import read_inventory
from obspy.core.stream import read

from sdaas.core import traces_idscores

# Load a Stream object and its inventory
# (use as example the test directory of the package):
stream = read('./tests/data/GE.FLT1..HH?.mseed')
inventory = read_inventory('./tests/data/GE.FLT1.xml')

# Compute the Stream anomaly score:
output = traces_idscores(stream, inventory)
"""
    locals_ = {}
    exec_snippet(snippet, locals_)
    assert np.allclose(locals_['output'][1], [0.45729656, 0.45199387, 0.45113142],
                       atol=0.01, rtol=0)
    ids = locals_['output'][0]  # check also ids:
    assert ids[0][0] == 'GE.FLT1..HHE'
    assert ids[1][0] == 'GE.FLT1..HHN'
    assert ids[2][0] == 'GE.FLT1..HHZ'


def test_snippet_03():
    snippet = """
from obspy.core.inventory.inventory import read_inventory
from obspy.core.stream import read

from sdaas.core import traces_idscores

# Load a Stream object and its inventory
# (use as example the test directory of the package):
stream = read('./tests/data/GE.FLT1..HH?.mseed')
inventory = read_inventory('./tests/data/GE.FLT1.xml')

# Compute the Stream anomaly score:
output = traces_idscores(stream, inventory, idfunc=lambda t: t.get_id())
"""
    locals_ = {}
    exec_snippet(snippet, locals_)
    assert np.allclose(locals_['output'][1], [0.45729656, 0.45199387, 0.45113142],
                       atol=0.01, rtol=0)
    ids = locals_['output'][0]  # check also ids:
    assert ids[0] == 'GE.FLT1..HHE'
    assert ids[1] == 'GE.FLT1..HHN'
    assert ids[2] == 'GE.FLT1..HHZ'


def test_snippet_04():
    snippet = """
from sdaas.core import streams_scores
from sdaas.core import streams_idscores
from sdaas.core import trace_score
"""
    locals_ = {}
    exec_snippet(snippet, locals_) # nothing to test (just that it import correctly)


def test_snippet_05():
    snippet = """
from obspy.core.inventory.inventory import read_inventory
from obspy.core.stream import read

from sdaas.core import streams_scores

# Load a Stream objects and its inventory
# (use as example the test directory of the package
# and mock a list of streams by loading twice the same Stream):
streams = [read('./tests/data/GE.FLT1..HH?.mseed'),
           read('./tests/data/GE.FLT1..HH?.mseed')]
inventory = read_inventory('./tests/data/GE.FLT1.xml')

# Compute Streams scores:
output = streams_scores(streams, inventory)
"""
    locals_ = {}
    exec_snippet(snippet, locals_)
    assert np.allclose(locals_['output'],
                       [0.45729656, 0.45199387, 0.45113142, 0.45729656, 0.45199387, 0.45113142],
                       atol=0.01, rtol=0)


def test_snippet_06():
    snippet = """
from obspy.core.inventory.inventory import read_inventory
from obspy.core.stream import read

from sdaas.core import trace_features, aa_scores

# Load a Stream object and its inventory
# (use as example the test directory of the package
# and mock a list of streams by loading twice the same Stream):
streams = [read('./tests/data/GE.FLT1..HH?.mseed'),
           read('./tests/data/GE.FLT1..HH?.mseed')]
inventory = read_inventory('./tests/data/GE.FLT1.xml')

# Compute Streams scores:
feats = []
for stream in streams:
    for trace in stream:
        feats.append(trace_features(trace, inventory))
output = aa_scores(feats)
"""
    locals_ = {}
    exec_snippet(snippet, locals_)
    assert np.allclose(locals_['output'],
                       [0.45729656, 0.45199387, 0.45113142, 0.45729656, 0.45199387, 0.45113142],
                       atol=0.01, rtol=0)


def exec_snippet(code, locals_):
    tmp = sys.stdout
    buffer = StringIO()
    sys.stdout = buffer
    cwd = os.getcwd()
    os.chdir(dirname(dirname(__file__)))
    try:
        exec(code, globals(), locals_)
        return buffer.getvalue()
    except Exception as err:
        raise ValueError('Error in a Python snippet, fix and UPDATE README.md in case: %s, %s' %
                         (str(err.__class__.__name__), str(err))) from None
    finally:
        # Restore the original stdout!
        sys.stdout = tmp
        # restore cwd:
        os.chdir(cwd)


if __name__ == "__main__":
    #  import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
