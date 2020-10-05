'''
Tests the snippets providede in the README to assure that they work. Also,
MODIFIES the README SO A COMMIT MIGHT BE NECESSARY AFTER THIS RUN (a message
is printed in case, if no message is shown, then the readme was not changed)

Created on 28 Sep 2020

@author: Riccardo Z. <rizac@gfz-potsdam.de>
'''
import unittest
from os.path import join, dirname, relpath, abspath, basename

from obspy.core.stream import read
from obspy.core.inventory.inventory import read_inventory


class Test(unittest.TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_readme(self):
        '''tests the readme
        '''
        ret = create_readme_snippet().strip()
        readmefile = join(dirname(dirname(__file__)), 'README.md')
        with open(readmefile) as fle:
            content = fle.read()
        thisfilepath = relpath(abspath(__file__), dirname(readmefile))
        tag1 = (f'<!--AUTO GENERATED SNIPPET DO NOT EDIT -->\n'
                f'<!-- (see {thisfilepath} for details) -->')
        tag2 = f'<!-- END AUTOGENERATED SNIPPET -->'
        idx1, idx2 = content.index(tag1), content.index(tag2)
        if idx1 < 0 or idx2 < 0:
            return
        old_ret = content[idx1 + len(tag1):idx2].strip()
        if ret == old_ret:
            return
        content1 = content[:idx1].strip()
        content2 = content[idx2 + len(tag2):].strip()
        if content1:
            content1 += '\n\n'
        if content2:
            content2 = '\n\n' + content2
        content = (f"{content1}{tag1}\n\n{ret.strip()}\n\n{tag2}{content2}")
        with open(readmefile, 'w') as fle:
            content = fle.write(content)

        print(f'WARNING: {basename(readmefile)} HAS BEEN MODIFIED \n'
              f'WITH THE AUTO-GENERATED CODE SNIPPET IN {basename(__file__)}\n'
              'YOU WILL NEED TO COMMIT THE CHANGOES')


def create_readme_snippet():
    dataroot = join(dirname(__file__), 'data')
    stream = read(join(dataroot, 'GE.FLT1..HH?.mseed'))
    inventory = read_inventory(join(dataroot, 'GE.FLT1.xml'))

    stream2 = read(join(dataroot, 'trace_GE.APE.mseed'))
    inventory2 = read_inventory(join(dataroot, 'inventory_GE.APE.xml'))

    streams = [stream2, stream]

    loc = locals()

    content = ''

    content += '\n**Examples**: '

    title = ('Compute the scores in a stream or iterable of traces '
             '(e.g. list. tuple):')
    code = '''from sdaas.core import traces_scores
traces_scores(stream, inventory)'''
    content += makesnippet(title, code, locals())

    title = ('Compute the scores in a stream or iterable of traces, '
             'getting also the traces id (seed_id, start, end):')
    code = '''from sdaas.core import traces_idscores
traces_idscores(stream, inventory)'''
    content += makesnippet(title, code, locals())

    title = ('Same as above, with custom id function given as the seed id '
             '(`trace.get_id()` in ObsPy):')
    code = '''from sdaas.core import traces_idscores
traces_idscores(stream, inventory, idfunc=lambda t: t.get_id())'''
    content += makesnippet(title, code, locals())

    title = ('You can also compute scores and ids from terable of streams '
             '(e.g., when reading from files)...')
    code = '''from sdaas.core import streams_scores
from sdaas.core import streams_idscores'''
    content += makesnippet(title, code, locals(), False)

    title = ('... or from a single trace:')
    code = '''from sdaas.core import trace_score'''
    content += makesnippet(title, code, locals(), False)

    streams = [stream] * 5

    title = 'Getting anomaly score from several streams'
    code = '''from sdaas.core import streams_scores
streams_scores(streams, inventory)'''
    content += makesnippet(title, code, locals())

    title = ('Same as above, computing the features and the scores separately '
             'for more control (note that for better performances, scores are '
             'computed once on all features and not inside a for loop):')
    code = '''from sdaas.core import trace_features, aa_scores
feats = []
for stream in streams:
    for trace in stream:
        feats.append(trace_features(trace, inventory))
aa_scores(feats)'''
    content += makesnippet(title, code, locals())

    content += '''*Note* `trace_features` returns a vector (numpy array) representing
a given trace and which is used as input of our machine learning Isolation Forest algorithm.
Currently, it consists of a mono-dimensional vector (numpy array of length 1)
of the waveform power spectral density (PSD) computed at 5 s period.
`aa_scores` is the low-level function that computes amplitude anomaly score from an array
of feature vectors (Nx1 numpy array)'''

    return content


def makesnippet(title, code, locals_, eval_last_line=True):
    code_lines = code.strip().split('\n')
    if eval_last_line:
        code = "\n".join(code_lines[:-1]) + '\n__var__= (' + code_lines[-1] + ")"
    exec(code, globals(), locals_)
    code_str = '\n'.join(f'>>> {_}' for _ in code_lines)
    result = repr(locals_['__var__']) + '\n' if eval_last_line else ''
    return f'''{title.strip()}
```python
{code_str}
{result}```

'''


if __name__ == "__main__":
    #  import sys;sys.argv = ['', 'Test.testName']
    unittest.main()